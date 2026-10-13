# 启动与使用：v0.2 离线工作台

AI-Novel-Writer 最终希望把长篇小说创作中的大纲、人物、正文、审核改写与历史记录放在一个平台中。原有 `README.md` 描述长期目标，本文件说明当前实际完成的范围。

## 现在已经有什么

- 可打开的浏览器写作界面，使用本项目自己的设计。
- 小说项目、全书大纲、章节细纲、每章 IDEA、人物、世界观和文风规则的手动管理。
- SQLite 磁盘保存、关闭重开读取、章节版本查看和恢复、正式章节确认保护。
- 本地 Skills Markdown 导入、原文查看，以及面向作者与 AI 的软件内使用指南。
- JSON 导出、基础数据校验、虚构示例和自动测试。

真实模型 API、自动正文生成、审核改写、自动一致性检查和全书大纲自动更新仍未启用。无需开通 AI 服务。

## Windows 一键启动

1. 打开项目根目录，双击 `start.bat`。
2. 浏览器自动打开 `http://127.0.0.1:8765`；若没有自动打开，复制启动窗口显示的地址到浏览器。
3. 保留启动窗口，点击“＋ 创建小说”开始。各页面编辑完成后点击保存，软件不会自动保存文本编辑。
4. 完成写作后先保存，再在启动窗口按 Ctrl+C 停止软件。

脚本优先使用已安装的 Python 3.11+，也支持当前电脑现有的 Codex Python 运行环境。它不会下载依赖或请求模型。换到其他电脑，需要先配置 Python 3.11 或更高版本。

## 用命令启动

在项目根目录运行：

```powershell
python run.py
```

常用选项：

```powershell
python run.py --port 8766
python run.py --no-browser
python run.py --database "D:/我的小说资料/novels.sqlite3"
```

如果默认端口已被使用，先查看是否已经打开软件，或改用 8766。软件只接受本机访问；自定义数据库使用指定位置，默认数据库始终基于项目目录，与打开终端的位置无关。

## 怎样查看

先看本文件，再看 `user-guide.md` 或软件内的“使用指南”。开发结构见 `architecture.md`，数据关联见 `data-models.md`；可对照 `examples/sample-novel/novel.json` 阅读，后续安排见 `roadmap.md`。

可以把 JSON 理解为有固定标签的资料卡：`title` 是书名，`content` 是正文，`id` 是不会因改名而变化的编号。Python 数据类则规定每张资料卡允许包含哪些字段。

## 怎样验证

基础代码使用 Python 3.11 或更高版本，只依赖标准库，无需 API 密钥或第三方运行依赖。以下命令用于检查项目基础；启动界面使用上面的 `run.py`。

在项目根目录打开终端，先确认 Python 可用：

```powershell
python --version
```

然后运行：

```powershell
python scripts/validate_example.py
python -m unittest discover -s tests -v
```

第一条命令显示虚构示例校验结果；第二条验证数据、真实磁盘保存、事务回滚、冲突、确认保护、Skills、HTTP 与启动入口，成功时最后显示 `OK`。测试使用临时数据库，不修改作者的小说。

如果 `python` 命令不可用，说明这台电脑的终端尚未配置 Python。可以让开发者使用已安装 Python 的完整路径验证，再单独配置日常开发环境。无需为本阶段购买或开通 AI 服务。

启动与验证命令直接读取 `src/`，不用执行 `pip install`。`pyproject.toml` 记录项目元信息和打包配置；打包工具不是启动所需依赖。

## 自己的小说放在哪里

所有小说和导入的 Skills 默认保存在 `data/novels.sqlite3`，第一次启动时自动创建。页面点击保存后写入磁盘，关闭重开可读取。`data/` 和数据库文件后缀已加入 Git 忽略规则，避免提交私人正文。

Git 忽略规则不能代替备份。顶部“导出已保存数据”可下载当前小说 JSON，但不含全局 Skills；完整备份应先保存、关闭软件，再复制整个数据库。当前没有导入 JSON 备份的界面。详见 `user-guide.md`。

GitHub 用于保存软件代码和公开示例，软件里的版本记录用于保存小说内容历史；两者用途不同。上传说明见 `github-sync.md`。

## 可选浏览器验收（开发者）

`tests/e2e-smoke.cjs` 使用 Playwright 和临时数据库，验证创建、正文保存、刷新、版本恢复、服务重启、Skills 和使用指南，并检查窄屏及 JavaScript 错误。

已有 Node.js、Playwright 和浏览器的环境可运行：

```powershell
$env:NOVEL_WRITER_PYTHON = "python"
$env:NOVEL_WRITER_BROWSER = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
node tests/e2e-smoke.cjs
```

需要时使用 `NODE_PATH` 指向已有 Playwright 包目录，`NOVEL_WRITER_SCREENSHOT` 指定验收截图的输出路径。浏览器测试环境不是作者使用软件所需依赖。
