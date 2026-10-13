"""章节版本：追加内容快照，恢复时创建新版本。"""

from dataclasses import asdict

from novel_writer.application.fields import check_fields, find
from novel_writer.domain.models import DataValidationError, VersionRecord, utc_now

MODULE = {"id": "versions", "name": "章节版本管理", "status": "ready", "description": "每次保存保留正文快照，可查看和恢复为新版本。"}


def record(document, entity_type: str, entity, note: str):
    entity.updated_at = utc_now()
    snapshot = asdict(entity)
    snapshot.pop("current_version_id", None)
    previous = [item for item in document.versions if (item.entity_type, item.entity_id) == (entity_type, entity.id)]
    last = max(previous, key=lambda item: item.version_number) if previous else None
    version = VersionRecord(
        project_id=document.project.id, entity_type=entity_type, entity_id=entity.id,
        version_number=1 if last is None else last.version_number + 1,
        previous_version_id=None if last is None else last.id, snapshot=snapshot, change_note=note,
    )
    document.versions.append(version)
    if entity_type == "chapter":
        entity.current_version_id = version.id
    return version


def require_authorization(chapter, values):
    permission = values.get("authorize_confirmed", False)
    if type(permission) is not bool:
        raise DataValidationError("作者确认必须是明确的布尔值")
    if chapter.status == "confirmed" and not permission:
        raise DataValidationError("这是已确认章节，修改或恢复前需要作者明确确认")


def restore(document, values):
    check_fields(values, {"chapter_id", "version_id", "authorize_confirmed"})
    chapter = find(document.chapters, values.get("chapter_id"), "章节")
    version = find(document.versions, values.get("version_id"), "版本")
    if (version.entity_type, version.entity_id) != ("chapter", chapter.id):
        raise DataValidationError("此版本不属于选中的章节正文")
    require_authorization(chapter, values)
    chapter.title = version.snapshot["title"]
    chapter.content = version.snapshot["content"]
    chapter.status = "draft"
    record(document, "chapter", chapter, f"恢复正文第 {version.version_number} 版，追加为新草稿；保留当前章节顺序")
