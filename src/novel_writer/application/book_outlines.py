"""全书大纲管理；当前由作者手动编辑。"""

from novel_writer.application.fields import check_fields, update_text
from novel_writer.application.versions import record
from novel_writer.domain.models import BookOutline

MODULE = {"id": "book_outlines", "name": "全书大纲管理", "status": "ready", "description": "手动编辑主题、故事起点、主线与结局。"}


def save(document, values):
    names = ("theme", "premise", "main_plot", "ending")
    check_fields(values, set(names))
    if document.book_outline is None:
        document.book_outline = BookOutline(project_id=document.project.id)
    update_text(document.book_outline, values, names)
    record(document, "book_outline", document.book_outline, "手动保存全书大纲")
