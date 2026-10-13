"""技能资料的独立 SQLite 表；只追加导入记录，不改项目及数据库版本。"""

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class SkillsRepository:
    def __init__(self, database_path: str | Path):
        self.path = Path(database_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS skills ("
                "id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, "
                "imported_at TEXT NOT NULL, primary_path TEXT NOT NULL, files_json TEXT NOT NULL)"
            )

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA synchronous = FULL")
            with connection:
                yield connection
        finally:
            connection.close()

    def add(self, record: dict) -> dict:
        files_json = json.dumps(record["files"], ensure_ascii=False, allow_nan=False)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO skills (id, name, description, imported_at, primary_path, files_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (record["id"], record["name"], record["description"],
                 record["imported_at"], record["primary_path"], files_json),
            )
        return {**record, "files": json.loads(files_json)}

    def list_skills(self) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, name, description, imported_at, primary_path FROM skills "
                "ORDER BY imported_at DESC, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, skill_id: str) -> dict:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, name, description, imported_at, primary_path, files_json "
                "FROM skills WHERE id = ?", (skill_id,),
            ).fetchone()
        if row is None:
            raise KeyError("找不到这个技能资料")
        record = dict(row)
        record["files"] = json.loads(record.pop("files_json"))
        return record
