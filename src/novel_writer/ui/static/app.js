'use strict';

const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
let workspace = null, projects = [], token = '', view = 'project', writingPane = 'body';
let selectedChapter = '', selectedCharacter = '', selectedSkill = '';
let dirty = false, busy = false, createKind = 'project';
const disabledBeforeRequest = new Map();
const textareaValues = new Map();
const tabs = [['project', '项目资料'], ['outline', '全书大纲'], ['writing', '章节写作'], ['characters', '人物设定'], ['world', '世界观'], ['rules', '文风规则'], ['skills', 'Skills'], ['guide', '使用指南'], ['modules', '模块规划'], ['settings', '设置']];

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', 'X-Novel-Token': token, ...(options.headers || {}) } });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败，请保留输入后重试。');
  return result;
}

function notify(message, error = false) {
  $('#notification').hidden = false;
  $('#notification').textContent = message;
  $('#notification').classList.toggle('error', error);
}

function saveIndicator() {
  $('#save-state').textContent = busy ? '正在处理…' : dirty ? '未保存修改' : workspace ? `已保存 · ${workspace.revision}` : '尚未选择小说';
  $('#save-state').classList.toggle('unsaved', dirty);
}

function setBusy(value) {
  busy = value;
  if (value) {
    document.querySelectorAll('button, input, textarea, select').forEach(element => { disabledBeforeRequest.set(element, element.disabled); element.disabled = true; });
  } else {
    disabledBeforeRequest.forEach((wasDisabled, element) => { element.disabled = wasDisabled; });
    disabledBeforeRequest.clear();
    $('#reload-project').disabled = !workspace;
  }
  saveIndicator();
}

function mayLeave() {
  return !busy && (!dirty || window.confirm('当前内容尚未保存。离开会放弃这些修改，是否继续？'));
}

function field(name, label, value = '', multiline = false, required = false, scope = 'edit', extraClass = '') {
  const id = `${scope}-${name}`;
  if (multiline) textareaValues.set(id, value);
  const input = multiline
    ? `<textarea id="${id}" name="${name}" class="${extraClass}" ${required ? 'required' : ''}></textarea>`
    : `<input id="${id}" name="${name}" value="${escapeHTML(value)}" ${required ? 'required' : ''} autocomplete="off">`;
  return `<div class="field"><label for="${id}">${label}</label>${input}</div>`;
}

function panelForm(action, title, description, body, button) {
  return `<form class="panel" data-action="${action}"><div class="panel-heading"><div><h2>${title}</h2><p class="hint">${description}</p></div></div>${body}<div class="form-footer"><span>点击保存后写入本地数据库</span><button type="submit" class="primary">${button}</button></div></form>`;
}

function renderLibrary() {
  $('#project-count').textContent = projects.length;
  $('#project-list').innerHTML = projects.length ? projects.map(project => `<button class="book-link ${workspace?.document.project.id === project.id ? 'active' : ''}" data-project="${escapeHTML(project.id)}"><span>${escapeHTML(project.title)}</span><small>保存编号 ${project.revision}</small></button>`).join('') : '<p class="sidebar-empty">书架还是空的。创建你的第一本小说。</p>';
}

async function refreshProjects() {
  projects = await api('/api/projects');
  renderLibrary();
}

function renderChrome() {
  const project = workspace?.document.project;
  $('#book-title').textContent = project?.title || '把故事，一章章写下来。';
  $('#book-description').textContent = project ? `${project.author || '未填写作者'} · ${project.genre || '未填写类型'} · ${workspace.document.chapters.length} 章` : '从一个想法开始，让人物、情节与正文各归其位。';
  $('#reload-project').disabled = !workspace;
  $('#export-project').hidden = !workspace;
  if (project) $('#export-project').href = `/api/projects/${project.id}/export`;
  $('#tabs').innerHTML = tabs.map(([id, name]) => `<button data-view="${id}" class="${view === id ? 'active' : ''}" ${!workspace && !['skills', 'guide', 'modules', 'settings'].includes(id) ? 'disabled' : ''}>${name}</button>`).join('');
  renderLibrary();
  saveIndicator();
}

async function openProject(id, preserveView = false) {
  if (!mayLeave()) return;
  setBusy(true);
  try {
    workspace = await api(`/api/projects/${encodeURIComponent(id)}`);
    dirty = false;
    selectedChapter = workspace.document.chapters.some(item => item.id === selectedChapter) ? selectedChapter : workspace.document.chapters[0]?.id || '';
    selectedCharacter = workspace.document.characters[0]?.id || '';
    if (!preserveView) view = 'project';
    sessionStorage.setItem('novel-project', id);
    await renderMain();
  } catch (error) { notify(error.message, true); } finally { setBusy(false); }
}

async function perform(action, values) {
  if (busy || !workspace) return;
  setBusy(true);
  let committed = false;
  try {
    const saved = await api(`/api/projects/${workspace.document.project.id}/actions`, { method: 'POST', body: JSON.stringify({ action, fields: values, expected_revision: workspace.revision }) });
    workspace = saved;
    committed = true;
    dirty = false;
    if (action === 'add_chapter') selectedChapter = workspace.document.chapters.at(-1).id;
    if (action === 'add_character') selectedCharacter = workspace.document.characters.at(-1).id;
    await renderMain();
    await refreshProjects();
    notify(`已保存到本地 · 保存编号 ${workspace.revision}`);
    return true;
  } catch (error) {
    notify(committed ? `内容已保存，但页面刷新失败：${error.message}。请重新读取，不要重复创建。` : error.message, true);
    return committed;
  } finally { setBusy(false); }
}

function renderProject() {
  const p = workspace.document.project;
  return panelForm('save_project', '这本书的起点', '整理基本资料。作者和类型可以稍后补充。',
    '<div class="field-grid">' + field('title', '书名', p.title, false, true) + field('author', '作者', p.author) + field('genre', '小说类型', p.genre) + '</div>' + field('summary', '小说简介', p.summary, true), '保存项目资料');
}

function renderOutline() {
  const outline = workspace.document.book_outline || {};
  return panelForm('save_book_outline', '给故事一条完整的主线', '先写主题与结局，再逐步补足故事的起承转合。',
    field('theme', '核心主题', outline.theme) + field('premise', '故事起点', outline.premise, true) + field('main_plot', '全书主线', outline.main_plot, true) + field('ending', '预期结局', outline.ending, true), '保存全书大纲');
}

function renderWriting() {
  const chapters = workspace.document.chapters;
  if (!chapters.length) return '<div class="empty-state"><h2>第一章，从这里开始</h2><p>先建立章节，再记录 IDEA、细纲和正文。它们会分别保存。</p><button class="primary" data-create="chapter">＋ 新建章节</button></div>';
  const chapter = chapters.find(item => item.id === selectedChapter) || chapters[0];
  selectedChapter = chapter.id;
  const outline = workspace.document.chapter_outlines.find(item => item.chapter_id === chapter.id) || {};
  const toolbar = `<div class="chapter-toolbar"><div class="field"><label for="chapter-select">当前章节</label><select id="chapter-select" data-passive>${chapters.map(item => `<option value="${item.id}" ${item.id === chapter.id ? 'selected' : ''}>第 ${item.number} 章 · ${escapeHTML(item.title)}</option>`).join('')}</select></div><button data-create="chapter">＋ 新建章节</button></div>`;
  const subtabs = '<div class="subtabs">' + [['body', '正文'], ['idea', 'IDEA'], ['outline', '章节细纲']].map(([id, title]) => `<button data-pane="${id}" class="${writingPane === id ? 'active' : ''}">${title}</button>`).join('') + '</div>';
  let form;
  const idField = `<input type="hidden" name="chapter_id" value="${chapter.id}">`;
  if (writingPane === 'idea') {
    form = panelForm('save_idea', '留下本章的灵感', '一句话、一个场景或一段对话，都可以先记录在这里。', idField + field('content', '本章 IDEA', workspace.ideas[chapter.id] || '', true, false, 'edit', 'tall'), '保存 IDEA');
  } else if (writingPane === 'outline') {
    form = panelForm('save_chapter_outline', '把想法整理成细纲', '说明这一章发生什么，以及它在全书中的作用。', idField + field('core_idea', '核心情节', outline.core_idea, true) + field('objective', '本章目标', outline.objective, true) + field('story_time', '剧情时间', outline.story_time), '保存章节细纲');
  } else {
    const status = `<div class="field"><label for="chapter-status">正文状态</label><select id="chapter-status" name="status"><option value="draft" ${chapter.status === 'draft' ? 'selected' : ''}>草稿</option><option value="confirmed" ${chapter.status === 'confirmed' ? 'selected' : ''}>已确认</option></select></div>`;
    const authorization = chapter.status === 'confirmed' ? '<label class="check-label"><input type="checkbox" name="authorize_confirmed" required>我确认修改这章正式内容，并保留此前版本。</label>' : '';
    form = panelForm('save_chapter', '写下这一章', '每次保存都会追加版本。正文中的换行与空格会原样保留。', idField + field('title', '标题', chapter.title, false, true) + field('content', '正文', chapter.content, true, false, 'edit', 'body-editor') + status + authorization, '保存正文');
  }
  const versions = workspace.document.versions.filter(item => item.entity_type === 'chapter' && item.entity_id === chapter.id).slice().reverse();
  return toolbar + subtabs + `<div class="editor-grid"><div>${form}<p class="hint">生成正文、DeepSeek 审核、Gemini 修改：待接入模型，本版暂未开放。</p></div><aside class="panel history-panel"><h3>每一版，都留在这里</h3><div class="field"><label for="version-select">历史版本</label><select id="version-select" data-passive>${versions.map(item => `<option value="${item.id}">正文第 ${item.version_number} 版</option>`).join('')}</select></div><p id="version-note" class="hint"></p><pre id="version-preview" class="version-preview"></pre><button id="restore-version" type="button">恢复此版为新草稿</button><p class="hint">恢复后原有版本继续保留，当前章节顺序保持不变。</p></aside></div>`;
}

function showVersion() {
  const id = $('#version-select')?.value;
  if (!id) return;
  const version = workspace.document.versions.find(item => item.id === id);
  $('#version-preview').textContent = version.snapshot.content || '这一版尚无正文。';
  $('#version-note').textContent = version.change_note + ' · ' + new Date(version.created_at).toLocaleString('zh-CN');
}

function renderCharacters() {
  const characters = workspace.document.characters;
  if (!characters.length) return '<div class="empty-state"><h2>认识故事里的人</h2><p>记录人物的身份、性格和背景，让后续创作有据可查。</p><button class="primary" data-create="character">＋ 新建人物</button></div>';
  const character = characters.find(item => item.id === selectedCharacter) || characters[0];
  selectedCharacter = character.id;
  return `<div class="chapter-toolbar"><div class="field"><label for="character-select">当前人物</label><select id="character-select" data-passive>${characters.map(item => `<option value="${item.id}" ${item.id === character.id ? 'selected' : ''}>${escapeHTML(item.name)}</option>`).join('')}</select></div><button data-create="character">＋ 新建人物</button></div>` +
    panelForm('save_character', '人物设定', '改名不会改变人物编号，历史设定随版本保留。', `<input type="hidden" name="character_id" value="${character.id}">` + '<div class="field-grid">' + field('name', '人物姓名', character.name, false, true) + field('role', '身份与作用', character.role) + '</div>' + field('personality', '性格', character.personality, true) + field('background', '背景经历', character.background, true) + field('notes', '其他设定', character.notes, true), '保存人物');
}

async function renderModules() {
  const modules = await api('/api/modules');
  const labels = { ready: '可使用', partial: '部分完成', planned: '待实现' };
  return '<div class="panel-heading"><div><h2>模块各自独立，按阶段完善</h2><p class="hint">查看当前能力；待实现项目不会运行模型或返回虚构结果。</p></div></div><div class="capability-list">' + modules.map(item => `<div class="capability"><strong>${escapeHTML(item.name)}</strong><p>${escapeHTML(item.description)}</p><span class="badge ${item.status}">${labels[item.status]}</span></div>`).join('') + '</div>';
}

async function renderSettings() {
  const settings = await api('/api/settings');
  return `<section class="panel"><h2>当前运行设置</h2><p class="hint">本版不需要模型密钥，所有模型调用都处于关闭状态。</p><div class="setting-row"><span>运行方式</span><span class="badge ready">仅本机 · 离线编辑</span></div><div class="setting-row"><span>真实模型 API</span><span class="badge">未启用</span></div><div class="setting-row"><span>DeepSeek 环境变量</span><span>${settings.providers.deepseek.key_configured ? '已配置（不显示密钥）' : '未配置'}</span></div><div class="setting-row"><span>Gemini 环境变量</span><span>${settings.providers.gemini.key_configured ? '已配置（不显示密钥）' : '未配置'}</span></div><h3>本地数据位置</h3><p class="path-display">${escapeHTML(settings.database_path)}</p><p class="hint">关闭软件后可以复制整个数据库文件备份。顶部“导出已保存数据”可下载当前小说的 JSON 副本；当前尚未提供导入备份按钮。</p></section>`;
}

async function renderSkills() {
  const skills = await api('/api/skills');
  if (!skills.some(item => item.id === selectedSkill)) selectedSkill = skills[0]?.id || '';
  const skill = selectedSkill ? await api(`/api/skills/${selectedSkill}`) : null;
  return `<section class="panel skill-import"><h2>把自己的 Skills 放进资料库</h2><p class="hint">单个 SKILL.md 或包含它的技能文件夹。只保存 Markdown 文字，不执行脚本；最多 100 个文件，总计 2 MiB。</p><div class="field-grid"><div class="field"><label for="skill-file">选择 SKILL.md</label><input id="skill-file" type="file" accept=".md" data-passive></div><div class="field"><label for="skill-folder">或选择技能文件夹</label><input id="skill-folder" type="file" webkitdirectory multiple data-passive></div></div><button id="import-skill" class="primary" type="button">导入所选资料</button><p class="hint">文件夹中的非 Markdown 文件会跳过。每次只选择一个技能；导入后不会自动安装到 Codex。</p></section><div class="skills-grid"><section class="panel"><h3>已导入技能 · ${skills.length}</h3>${skills.length ? skills.map(item => `<button class="skill-item ${item.id === selectedSkill ? 'active' : ''}" data-skill="${item.id}">${escapeHTML(item.name)}</button>`).join('') : '<p class="hint">还没有导入资料。</p>'}</section><section class="panel">${skill ? `<h2>${escapeHTML(skill.name)}</h2><p class="hint">${escapeHTML(skill.description || '查看原始资料。')}</p><div class="field"><label for="skill-source-select">资料文件</label><select id="skill-source-select" data-passive>${skill.files.map(item => `<option value="${escapeHTML(item.path)}" ${item.path === skill.primary_path ? 'selected' : ''}>${escapeHTML(item.path)}</option>`).join('')}</select></div><textarea id="skill-source" class="skill-source" readonly aria-label="技能原文" data-passive></textarea>` : '<h2>资料会完整保留</h2><p class="hint">导入后可以在这里查看技能说明和参考文档。后续接入 AI 时，再决定如何使用这些资料。</p>'}</section></div>`;
}

async function showSkillSource() {
  const selection = $('#skill-source-select');
  if (!selection) return;
  const skill = await api(`/api/skills/${selectedSkill}`);
  $('#skill-source').value = skill.files.find(item => item.path === selection.value)?.content || '';
}

async function renderMain() {
  renderChrome();
  textareaValues.clear();
  let html;
  if (view === 'guide') {
    const response = await fetch('/guide.html');
    if (!response.ok) throw new Error('使用指南读取失败。');
    html = await response.text();
  } else if (view === 'modules') html = await renderModules();
  else if (view === 'settings') html = await renderSettings();
  else if (view === 'skills') html = await renderSkills();
  else if (!workspace) html = '<div class="empty-state welcome"><p class="eyebrow">A PLACE FOR YOUR STORIES</p><h2>一本长篇，需要一个安静的起点。</h2><p>大纲、人物、灵感与正文，都放在这本书里。<br>从第一章开始，也把每一次修改留下来。</p><button class="primary" data-create="project">创建第一本小说</button><div class="welcome-steps"><span><b>01</b>整理故事与人物</span><span><b>02</b>记录 IDEA，写下正文</span><span><b>03</b>保存每一版内容</span></div></div>';
  else if (view === 'project') html = renderProject();
  else if (view === 'outline') html = renderOutline();
  else if (view === 'writing') html = renderWriting();
  else if (view === 'characters') html = renderCharacters();
  else if (view === 'world') html = panelForm('save_worldbuilding', '故事发生的世界', '记录地点、组织、力量体系，以及不能随意改变的设定。', field('content', '世界观与设定', workspace.worldbuilding, true, false, 'edit', 'tall'), '保存世界观');
  else if (view === 'rules') html = panelForm('save_writing_rules', '保持这本书的声音', '写下叙事视角、语言节奏和表达偏好，供后续写作参考。', field('content', '文风与写作规则', workspace.writing_rules, true, false, 'edit', 'tall'), '保存写作规则');
  $('#content').innerHTML = html;
  textareaValues.forEach((value, id) => { document.getElementById(id).value = value; });
  showVersion();
  if (view === 'skills') await showSkillSource();
}

function openCreate(kind) {
  if (!mayLeave()) return;
  createKind = kind;
  $('#create-form').reset();
  $('#dialog-error').textContent = '';
  $('#dialog-title').textContent = kind === 'project' ? '创建小说' : kind === 'chapter' ? '新建章节' : '新建人物';
  $('#dialog-fields').innerHTML = kind === 'project'
    ? field('title', '小说名称', '', false, true, 'new') + field('author', '作者', '', false, false, 'new') + field('genre', '小说类型', '', false, false, 'new')
    : kind === 'chapter' ? field('title', '章节标题', '', false, true, 'new') : field('name', '人物姓名', '', false, true, 'new');
  $('#create-dialog').showModal();
}

async function navigate(id) {
  if (!mayLeave()) return;
  dirty = false;
  view = id;
  $('#notification').hidden = true;
  setBusy(true);
  try { await renderMain(); } catch (error) { notify(error.message, true); } finally { setBusy(false); }
}

document.addEventListener('click', async event => {
  const button = event.target.closest('button');
  if (!button || busy) return;
  if (button.dataset.project) await openProject(button.dataset.project);
  else if (button.dataset.view) await navigate(button.dataset.view);
  else if (button.dataset.create) openCreate(button.dataset.create);
  else if (button.dataset.pane) {
    if (!mayLeave()) return;
    writingPane = button.dataset.pane;
    dirty = false;
    await renderMain();
  } else if (button.dataset.skill) {
    selectedSkill = button.dataset.skill;
    setBusy(true);
    try { await renderMain(); } catch (error) { notify(error.message, true); } finally { setBusy(false); }
  } else if (button.id === 'new-project') openCreate('project');
  else if (button.id === 'close-dialog') $('#create-dialog').close();
  else if (button.id === 'reload-project' && workspace) await openProject(workspace.document.project.id, true);
  else if (button.id === 'restore-version') {
    if (!mayLeave()) return;
    const chapter = workspace.document.chapters.find(item => item.id === selectedChapter);
    const question = chapter.status === 'confirmed' ? '这是已确认的正式章节。是否确认恢复所选内容为新草稿？原有版本会保留。' : '是否恢复所选版本为新草稿？当前内容也已保留在历史版本中。';
    if (!window.confirm(question)) return;
    writingPane = 'body';
    await perform('restore_chapter', { chapter_id: selectedChapter, version_id: $('#version-select').value, authorize_confirmed: chapter.status === 'confirmed' });
  } else if (button.id === 'import-skill') {
    const chosen = Array.from($('#skill-file').files.length ? $('#skill-file').files : $('#skill-folder').files);
    if (!chosen.length) { notify('请先选择 SKILL.md 或技能文件夹。', true); return; }
    const markdown = chosen.filter(file => file.name.toLowerCase().endsWith('.md'));
    if (markdown.length > 100 || markdown.reduce((sum, file) => sum + file.size, 0) > 2 * 1024 * 1024) { notify('Markdown 资料超过 100 个文件或 2 MiB 限制，请缩减后重试。', true); return; }
    setBusy(true);
    try {
      const decoder = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true });
      const files = await Promise.all(markdown.map(async file => ({ path: file.webkitRelativePath || file.name, content: decoder.decode(await file.arrayBuffer()) })));
      const imported = await api('/api/skills/import', { method: 'POST', body: JSON.stringify({ files }) });
      selectedSkill = imported.id;
      await renderMain();
      notify(`技能资料“${imported.name}”已保存到本地。${chosen.length > markdown.length ? '非 Markdown 文件已跳过。' : ''}`);
    } catch (error) { notify(error.message, true); } finally { setBusy(false); }
  }
});

$('#create-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  const values = Object.fromEntries(new FormData(event.currentTarget));
  if (createKind !== 'project') {
    if (await perform(createKind === 'chapter' ? 'add_chapter' : 'add_character', values)) $('#create-dialog').close();
    else $('#dialog-error').textContent = $('#notification').textContent;
    return;
  }
  setBusy(true);
  let committed = false;
  try {
    workspace = await api('/api/projects', { method: 'POST', body: JSON.stringify(values) });
    committed = true;
    selectedChapter = '';
    selectedCharacter = '';
    dirty = false;
    view = 'project';
    sessionStorage.setItem('novel-project', workspace.document.project.id);
    $('#create-dialog').close();
    await renderMain();
    await refreshProjects();
    notify('小说已创建并保存到本地。');
  } catch (error) {
    if (committed) notify(`小说已创建并保存，但页面刷新失败：${error.message}。请重新读取，不要重复创建。`, true);
    else $('#dialog-error').textContent = error.message;
  } finally { setBusy(false); }
});

$('#content').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy || !event.target.dataset.action) return;
  const values = Object.fromEntries(new FormData(event.target));
  if ('authorize_confirmed' in values) values.authorize_confirmed = event.target.elements.authorize_confirmed.checked;
  await perform(event.target.dataset.action, values);
});

$('#content').addEventListener('input', event => {
  if (event.target.closest('form[data-action]') && !event.target.hasAttribute('data-passive')) { dirty = true; saveIndicator(); }
});

$('#content').addEventListener('change', async event => {
  if (busy) return;
  const select = event.target;
  if (select.id === 'version-select') showVersion();
  else if (select.id === 'skill-source-select') {
    setBusy(true);
    try { await showSkillSource(); } catch (error) { notify(error.message, true); } finally { setBusy(false); }
  } else if (select.id === 'skill-file') $('#skill-folder').value = '';
  else if (select.id === 'skill-folder') $('#skill-file').value = '';
  else if (['chapter-select', 'character-select'].includes(select.id)) {
    if (!mayLeave()) { select.value = select.id === 'chapter-select' ? selectedChapter : selectedCharacter; return; }
    if (select.id === 'chapter-select') selectedChapter = select.value;
    else selectedCharacter = select.value;
    dirty = false;
    await renderMain();
  }
});

$('#export-project').addEventListener('click', event => {
  if (busy || (dirty && !window.confirm('导出文件只包含已经保存的内容，不含当前未保存修改。是否继续导出？'))) event.preventDefault();
});

document.querySelector('.brand').addEventListener('click', event => {
  if (!mayLeave()) event.preventDefault();
});

window.addEventListener('beforeunload', event => {
  if (dirty || busy) { event.preventDefault(); event.returnValue = ''; }
});

(async () => {
  setBusy(true);
  try {
    token = (await api('/api/session')).token;
    await refreshProjects();
    const savedId = sessionStorage.getItem('novel-project');
    if (projects.some(item => item.id === savedId)) workspace = await api(`/api/projects/${savedId}`);
    else if (projects.length) workspace = await api(`/api/projects/${projects[0].id}`);
    await renderMain();
  } catch (error) { notify(error.message, true); } finally { setBusy(false); }
})();
