"""SQLite 磁盘存储：事务保存、乐观锁、不可覆盖的项目快照。"""

from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from novel_writer.domain.models import DataValidationError, utc_now
from novel_writer.storage.json_codec import document_from_dict, document_to_dict


class ConflictError(ValueError):
    """其他窗口已经保存了新版本。"""


def validate_workspace(state: dict) -> dict:
    expected = {"workspace_version", "revision", "document", "ideas", "worldbuilding", "writing_rules"}
    if type(state) is not dict or set(state) != expected:
        raise DataValidationError("工作区字段不完整或含未知字段")
    if type(state["workspace_version"]) is not int or state["workspace_version"] != 1:
        raise DataValidationError("不支持此工作区格式版本")
    if type(state["revision"]) is not int or state["revision"] < 0:
        raise DataValidationError("保存编号必须是非负整数")
    document = document_from_dict(state["document"])
    if type(state["ideas"]) is not dict:
        raise DataValidationError("IDEA 必须按章节编号组织")
    chapter_ids = {chapter.id for chapter in document.chapters}
    for chapter_id, idea in state["ideas"].items():
        if chapter_id not in chapter_ids or type(idea) is not str:
            raise DataValidationError("IDEA 必须引用当前小说的章节，内容必须是文字")
    for name in ("worldbuilding", "writing_rules"):
        if type(state[name]) is not str:
            raise DataValidationError(f"{name} 必须是文字")
    normalized = deepcopy(state)
    normalized["document"] = document_to_dict(document)
    return normalized


class SQLiteRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise DataValidationError("数据库版本较新，请使用对应版本软件打开")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, revision INTEGER NOT NULL,
                    payload TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_snapshots (
                    project_id TEXT NOT NULL REFERENCES projects(id), revision INTEGER NOT NULL,
                    payload TEXT NOT NULL, saved_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, revision)
                );
                CREATE TRIGGER IF NOT EXISTS snapshots_no_update
                    BEFORE UPDATE ON project_snapshots BEGIN
                    SELECT RAISE(ABORT, '历史快照不可改写'); END;
                CREATE TRIGGER IF NOT EXISTS snapshots_no_delete
                    BEFORE DELETE ON project_snapshots BEGIN
                    SELECT RAISE(ABORT, '历史快照不可删除'); END;
                CREATE TRIGGER IF NOT EXISTS snapshots_no_replace
                    BEFORE INSERT ON project_snapshots
                    WHEN EXISTS (SELECT 1 FROM project_snapshots
                        WHERE project_id = NEW.project_id AND revision = NEW.revision) BEGIN
                    SELECT RAISE(ABORT, '历史快照不可替换'); END;
                PRAGMA user_version = 1;
                """
            )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def list_projects(self) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute("SELECT id, title, revision, updated_at FROM projects ORDER BY updated_at DESC, id").fetchall()
        return [dict(row) for row in rows]

    def get(self, project_id: str) -> dict:
        with self._connection() as connection:
            row = connection.execute("SELECT payload FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise KeyError("找不到这本小说")
        state = json.loads(row["payload"])
        return validate_workspace(state)

    def create(self, state: dict) -> dict:
        saved = validate_workspace(state)
        saved["revision"] = 1
        project = saved["document"]["project"]
        payload = json.dumps(saved, ensure_ascii=False, allow_nan=False)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM projects WHERE id = ?", (project["id"],)).fetchone():
                raise ConflictError("小说项目已存在，不能重复创建或覆盖")
            now = utc_now()
            connection.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", (project["id"], project["title"], 1, payload, now))
            connection.execute("INSERT INTO project_snapshots VALUES (?, ?, ?, ?)", (project["id"], 1, payload, now))
        return saved

    def save(self, state: dict, *, expected_revision: int) -> dict:
        saved = validate_workspace(state)
        if type(expected_revision) is not int or expected_revision < 1:
            raise DataValidationError("保存时需要有效的上次保存编号")
        saved["revision"] = expected_revision + 1
        project = saved["document"]["project"]
        payload = json.dumps(saved, ensure_ascii=False, allow_nan=False)
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT revision, payload FROM projects WHERE id = ?", (project["id"],)).fetchone()
            if row is None:
                raise KeyError("找不到这本小说")
            if row["revision"] != expected_revision:
                raise ConflictError("小说已在其他窗口更新，请先保留当前输入，再重新打开最新内容")
            old_versions = json.loads(row["payload"])["document"]["versions"]
            if saved["document"]["versions"][:len(old_versions)] != old_versions:
                raise DataValidationError("已有章节版本必须完整保留，不能改写或删除")
            now = utc_now()
            connection.execute("UPDATE projects SET title = ?, revision = ?, payload = ?, updated_at = ? WHERE id = ? AND revision = ?",
                               (project["title"], saved["revision"], payload, now, project["id"], expected_revision))
            connection.execute("INSERT INTO project_snapshots VALUES (?, ?, ?, ?)", (project["id"], saved["revision"], payload, now))
        return saved
