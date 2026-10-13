"""将本地 Markdown 技能资料原样导入资料库，不安装或执行技能。"""

from pathlib import Path, PurePosixPath

from novel_writer.application.fields import text
from novel_writer.domain.models import DataValidationError, new_id, utc_now
from novel_writer.storage.skills_repository import SkillsRepository

MODULE = {
    "id": "skills", "name": "本地 Skills 导入", "status": "ready",
    "description": "导入单个 SKILL.md 或同一技能文件夹中的 Markdown 资料，保留原文供查看。",
}
MAX_FILES = 100
MAX_BYTES = 2 * 1024 * 1024


def _validated_files(files) -> tuple[list[dict], dict]:
    if type(files) is not list or not 1 <= len(files) <= MAX_FILES:
        raise DataValidationError("每次请导入 1 至 100 个 Markdown 文件")
    copied = []
    paths = set()
    entrypoints = []
    total_bytes = 0
    for item in files:
        if type(item) is not dict or set(item) != {"path", "content"}:
            raise DataValidationError("每个文件必须且只能包含 path 和 content")
        path, content = item["path"], item["content"]
        if type(path) is not str or not path or type(content) is not str:
            raise DataValidationError("文件路径和内容必须是文字")
        parts = path.split("/")
        if ("\\" in path or ":" in path
                or any(ord(character) < 32 or ord(character) == 127 for character in path)
                or any(part in ("", ".", "..") or part.endswith((" ", ".")) for part in parts)):
            raise DataValidationError("文件路径必须是安全的相对路径，请用 / 分隔且不能包含 ..")
        if PurePosixPath(path).suffix.lower() != ".md":
            raise DataValidationError("只允许导入 .md 文本资料，不能导入脚本或其他文件")
        if path.casefold() in paths:
            raise DataValidationError("不能重复导入同一路径的文件")
        paths.add(path.casefold())
        try:
            total_bytes += len(path.encode("utf-8")) + len(content.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise DataValidationError("文件路径和内容必须能编码为 UTF-8 文本") from error
        if total_bytes > MAX_BYTES:
            raise DataValidationError("每次导入的 UTF-8 路径和内容总计不能超过 2 MiB")
        saved_file = {"path": path, "content": content}
        copied.append(saved_file)
        if parts[-1].casefold() == "skill.md":
            entrypoints.append(saved_file)
    if len(entrypoints) != 1:
        raise DataValidationError("每次导入必须恰好包含一个 SKILL.md")
    primary = entrypoints[0]
    folder = PurePosixPath(primary["path"]).parent
    if folder != PurePosixPath("."):
        for item in copied:
            if not PurePosixPath(item["path"]).is_relative_to(folder):
                raise DataValidationError("所有资料必须位于同一个 SKILL.md 所在文件夹内")
    return copied, primary


def _metadata(primary: dict) -> tuple[str, str]:
    """仅读取简单 frontmatter 文本字段；不加载 YAML 对象或执行指令。"""
    folder = PurePosixPath(primary["path"]).parent
    fallback = folder.name or "未命名技能"
    lines = primary["content"].lstrip("\ufeff").splitlines()
    metadata = {}
    if lines and lines[0].strip() == "---":
        closing = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
        if closing is not None:
            index = 1
            while index < closing:
                line = lines[index]
                index += 1
                if not line or line[0].isspace() or ":" not in line:
                    continue
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip()
                if key not in ("name", "description"):
                    continue
                if value in (">", ">-", ">+", "|", "|-", "|+"):
                    separator = " " if value.startswith(">") else "\n"
                    pieces = []
                    while index < closing and (not lines[index].strip() or lines[index][0].isspace()):
                        pieces.append(lines[index].strip())
                        index += 1
                    value = separator.join(pieces).strip()
                elif len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                    value = value[1:-1]
                metadata[key] = value
    return (metadata.get("name", "").strip() or fallback)[:200], metadata.get("description", "").strip()[:2000]


class SkillLibrary:
    def __init__(self, database_path: str | Path):
        self.repository = SkillsRepository(database_path)

    def import_files(self, files) -> dict:
        copied, primary = _validated_files(files)
        name, description = _metadata(primary)
        return self.repository.add({
            "id": new_id(), "name": name, "description": description,
            "imported_at": utc_now(), "primary_path": primary["path"], "files": copied,
        })

    def list_skills(self) -> list[dict]:
        return self.repository.list_skills()

    def get(self, skill_id: str) -> dict:
        return self.repository.get(text(skill_id, "技能资料编号", required=True))
