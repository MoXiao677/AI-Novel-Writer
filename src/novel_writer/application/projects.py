"""小说项目管理：创建项目和修改简介。"""

from novel_writer.application.fields import check_fields, text, update_text
from novel_writer.application.versions import record
from novel_writer.domain.models import NovelDocument, NovelProject
from novel_writer.storage.json_codec import document_to_dict

MODULE = {"id": "projects", "name": "小说项目管理", "status": "ready", "description": "创建、打开小说，管理书名、作者、类型与简介。"}


def create(values):
    check_fields(values, {"title", "author", "genre", "summary"})
    project = NovelProject(title=text(values.get("title"), "书名", required=True))
    update_text(project, values, ("author", "genre", "summary"))
    document = NovelDocument(project=project)
    record(document, "project", project, "创建小说项目")
    return {"workspace_version": 1, "revision": 0, "document": document_to_dict(document),
            "ideas": {}, "worldbuilding": "", "writing_rules": ""}


def save(document, values):
    check_fields(values, {"title", "author", "genre", "summary"})
    update_text(document.project, values, ("title", "author", "genre", "summary"), required=("title",))
    record(document, "project", document.project, "修改项目资料")
