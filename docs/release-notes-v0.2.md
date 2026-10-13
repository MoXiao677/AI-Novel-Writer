# v0.2 交付记录

交付日期：2026-10-13。目标是面向长篇小说的最小离线创作版本，后续再接入多模型。

## 已完成与使用方式

双击项目根目录的 `start.bat`，或运行 `python run.py`。在“使用指南”中查看作者操作和 AI 协作约定。采用独立界面设计；截图参考仅用于理解指南内容。

可使用小说、大纲、章节细纲、每章 IDEA、人物、世界观、文风、手工正文、章节历史和本地 Skills。内容保存在 SQLite，关闭重开仍可读取；正文恢复会追加新草稿，正式章节需要明确授权。界面显示当前保存状态，文本编辑需要手动保存。

## 新增文件

| 目录 | 文件 |
|---|---|
| 根目录 | `run.py`、`start.bat` |
| docs | `user-guide.md`、`release-notes-v0.2.md` |
| application：小说与资料 | `projects.py`、`book_outlines.py`、`chapter_outlines.py`、`ideas.py`、`characters.py`、`worldbuilding.py`、`writing_rules.py` |
| application：章节与公共业务 | `chapters.py`、`versions.py`、`fields.py`、`service.py`、`skill_import.py`、`settings.py` |
| application：模型与检查预留 | `generation.py`、`deepseek_review.py`、`gemini_revision.py`、`timeline.py`、`plot_logic.py`、`outline_updates.py`、`model_dispatch.py`、`quality.py` |
| storage | `sqlite_repository.py`、`skills_repository.py` |
| ui | `server.py` |
| ui/static | `index.html`、`app.js`、`style.css`、`favicon.svg`、`guide.html` |
| tests | `test_application.py`、`test_storage.py`、`test_skills.py`、`test_server.py`、`test_launcher.py`、`e2e-smoke.cjs` |

业务目录位于 `src/novel_writer/`。数据库 `data/novels.sqlite3` 在首次启动时自动建立，仅保留本地，不随代码上传。

## 更新的已有文件

保留原 README 的长期目标，并更新 `README.md`、`AGENTS.md`、`pyproject.toml`、`.gitignore`；同步更新 `docs/architecture.md`、`data-models.md`、`getting-started.md`、`github-sync.md`、`roadmap.md`，以及 application、storage、ui 的包说明。没有删除既有项目文件，旧内容可通过 Git 历史恢复。

## 验证结果

- 91 项 Python 自动测试通过，涵盖领域约束、磁盘重开、事务回滚、历史保护、冲突、Skills、HTTP 与启动入口。
- 虚构示例校验通过，原 schema_version=1 保持兼容。
- 真实 Edge 浏览器验收通过：创建小说和章节、中文正文保存、刷新读取、版本恢复、服务器重启、人物和世界观保存、Skills 导入原文、使用指南及 390px 窄屏。
- 验收包含两个回归场景：正文开头空行完整保留；数据库写入成功而书架刷新失败时避免重复创建。
- 双窗口冲突保留输入与正式章节授权由审查浏览器核对。
- 上传前检查 Git 差异、忽略规则和敏感内容，作者数据库不进入提交。

## 当前限制与建议下一步

所有真实模型调用仍关闭，自动审核、修改、时间线、逻辑、质量检查与大纲更新只是模块预留。密钥录入未开放；设置仅检查环境变量是否配置。

Skills 是 Markdown 资料导入，不执行脚本、不自动应用到创作。当前能导出 JSON，但没有导入备份按钮。完整项目快照会随内容和历史增加而增长，投入大规模长篇前需要优化存储。

建议先用练习项目完成一章、修改两次并恢复旧版，随后补齐备份导入和章节管理，再按作者授权接入第一个模型。
