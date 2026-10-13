"""每章 IDEA：作者随手记录的灵感，与结构化细纲独立。"""

from novel_writer.application.fields import check_fields, find, text

MODULE = {"id": "ideas", "name": "每章 IDEA 管理", "status": "ready", "description": "按章节独立记录灵感，随项目保存并保留项目快照。"}


def save(document, state, values):
    check_fields(values, {"chapter_id", "content"})
    chapter = find(document.chapters, values.get("chapter_id"), "章节")
    state["ideas"][chapter.id] = text(values.get("content"), "IDEA")
