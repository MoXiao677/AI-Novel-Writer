"""正文手动编辑；与未来的模型生成模块分离。"""

from novel_writer.application.fields import check_fields, find, text, update_text
from novel_writer.application.versions import record, require_authorization
from novel_writer.domain.models import Chapter, DataValidationError


def add(document, values):
    check_fields(values, {"title"})
    number = max((chapter.number for chapter in document.chapters), default=0) + 1
    chapter = Chapter(project_id=document.project.id, number=number, title=text(values.get("title"), "章节标题", required=True))
    document.chapters.append(chapter)
    record(document, "chapter", chapter, "新建章节")


def save(document, values):
    check_fields(values, {"chapter_id", "title", "content", "status", "authorize_confirmed"})
    chapter = find(document.chapters, values.get("chapter_id"), "章节")
    require_authorization(chapter, values)
    update_text(chapter, values, ("title", "content"), required=("title",))
    if "status" in values:
        status = text(values["status"], "章节状态")
        if status not in ("draft", "confirmed"):
            raise DataValidationError("章节状态必须是草稿或已确认")
        chapter.status = status
    record(document, "chapter", chapter, "作者手动保存正文")
