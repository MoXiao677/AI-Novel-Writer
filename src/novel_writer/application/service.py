"""业务入口：界面通过此服务访问独立模块和存储。"""

from novel_writer.application import (
    book_outlines, chapter_outlines, chapters, characters, deepseek_review, generation,
    gemini_revision, ideas, model_dispatch, outline_updates, plot_logic, projects,
    quality, settings, timeline, versions, worldbuilding, writing_rules,
)
from novel_writer.domain.models import DataValidationError, utc_now
from novel_writer.application.fields import text
from novel_writer.storage.json_codec import document_from_dict, document_to_dict
from novel_writer.storage.sqlite_repository import ConflictError


class NovelService:
    def __init__(self, repository):
        self.repository = repository

    def create(self, **values):
        return self.repository.create(projects.create(values))

    def list_projects(self):
        return self.repository.list_projects()

    def get(self, project_id):
        return self.repository.get(text(project_id, "项目编号", required=True))

    def settings(self):
        return settings.safe_status()

    def modules(self):
        modules = [projects, book_outlines, chapter_outlines, ideas, characters, worldbuilding,
                   generation, deepseek_review, gemini_revision, timeline, plot_logic, versions,
                   outline_updates, model_dispatch, writing_rules, quality, settings]
        result = [dict(module.MODULE) for module in modules]
        result.insert(11, {"id": "database", "name": "数据库管理", "status": "ready",
                           "description": "SQLite 事务保存、磁盘持久化、保存编号冲突检查与项目历史快照。"})
        return result

    def execute(self, project_id, action, values, *, expected_revision):
        project_id = text(project_id, "项目编号", required=True)
        action = text(action, "操作名称", required=True)
        if action in {"generate_body", "deepseek_review", "gemini_revision", "auto_update_outline"}:
            return model_dispatch.dispatch(action)
        state = self.repository.get(project_id)
        if type(expected_revision) is not int or expected_revision != state["revision"]:
            raise ConflictError("小说已更新，请保留当前输入并重新打开最新内容")
        document = document_from_dict(state["document"])
        handlers = {
            "save_project": projects.save, "save_book_outline": book_outlines.save,
            "add_character": characters.add, "save_character": characters.save,
            "add_chapter": chapters.add, "save_chapter": chapters.save,
            "save_chapter_outline": chapter_outlines.save, "restore_chapter": versions.restore,
        }
        if action in handlers:
            handlers[action](document, values)
        elif action == "save_idea":
            ideas.save(document, state, values)
        elif action == "save_worldbuilding":
            worldbuilding.save(state, values)
        elif action == "save_writing_rules":
            writing_rules.save(state, values)
        else:
            raise DataValidationError("未知操作")
        document.project.updated_at = utc_now()
        state["document"] = document_to_dict(document)
        return self.repository.save(state, expected_revision=expected_revision)
