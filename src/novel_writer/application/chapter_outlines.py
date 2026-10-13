"""章节细纲管理：与 IDEA 分开保存。"""

from novel_writer.application.fields import check_fields, find, update_text
from novel_writer.application.versions import record
from novel_writer.domain.models import ChapterOutline

MODULE = {"id": "chapter_outlines", "name": "章节细纲管理", "status": "ready", "description": "按章节编辑核心情节、目标与剧情时间说明。"}


def save(document, values):
    names = ("core_idea", "objective", "story_time")
    check_fields(values, {"chapter_id", *names})
    chapter = find(document.chapters, values.get("chapter_id"), "章节")
    outline = next((item for item in document.chapter_outlines if item.chapter_id == chapter.id), None)
    if outline is None:
        outline = ChapterOutline(project_id=document.project.id, chapter_id=chapter.id)
        document.chapter_outlines.append(outline)
    update_text(outline, values, names)
    record(document, "chapter_outline", outline, "手动保存章节细纲")
