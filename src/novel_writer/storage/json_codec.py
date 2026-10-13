"""JSON 转换与读取；不提供保存、覆盖或自动修改小说文件的操作。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from novel_writer.domain.models import (
    BookOutline, Chapter, ChapterOutline, Character, CharacterRelationship,
    DataValidationError, NovelDocument, NovelProject, ScenePlan, VersionRecord,
    VolumePlan, validate_document,
)


def _list_field(data: dict[str, Any], name: str) -> list[Any]:
    value = data.get(name, [])
    if type(value) is not list:
        raise DataValidationError(f"{name} 必须是列表")
    return value


def document_from_dict(data: dict[str, Any]) -> NovelDocument:
    """将 JSON 字典转换为数据对象，拒绝未知字段并校验关联。"""
    try:
        if type(data) is not dict or "schema_version" not in data:
            raise DataValidationError("小说 JSON 必须是包含 schema_version 的对象")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise DataValidationError("不支持此 schema_version；当前只支持 1")
        outline_data = data.get("book_outline")
        book_outline = None if outline_data is None else BookOutline(
            **{key: value for key, value in outline_data.items() if key != "volumes"},
            volumes=[VolumePlan(**item) for item in _list_field(outline_data, "volumes")],
        )
        characters = [
            Character(
                **{key: value for key, value in item.items() if key != "relationships"},
                relationships=[CharacterRelationship(**relation) for relation in _list_field(item, "relationships")],
            )
            for item in _list_field(data, "characters")
        ]
        chapter_outlines = [
            ChapterOutline(
                **{key: value for key, value in item.items() if key != "scenes"},
                scenes=[ScenePlan(**scene) for scene in _list_field(item, "scenes")],
            )
            for item in _list_field(data, "chapter_outlines")
        ]
        handled = {"project", "book_outline", "characters", "chapter_outlines", "chapters", "versions"}
        document = NovelDocument(
            **{key: value for key, value in data.items() if key not in handled},
            project=NovelProject(**data["project"]),
            book_outline=book_outline,
            characters=characters,
            chapter_outlines=chapter_outlines,
            chapters=[Chapter(**item) for item in _list_field(data, "chapters")],
            versions=[VersionRecord(**item) for item in _list_field(data, "versions")],
        )
    except (KeyError, TypeError, AttributeError) as error:
        raise DataValidationError(f"小说 JSON 的字段或结构有误：{error}") from error
    validate_document(document)
    return document


def document_to_dict(document: NovelDocument) -> dict[str, Any]:
    validate_document(document)
    return asdict(document)


def _reject_constant(value: str) -> None:
    raise DataValidationError(f"JSON 不允许包含 {value}")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise DataValidationError(f"JSON 包含重复字段：{key}")
        result[key] = value
    return result


def document_from_json(text: str) -> NovelDocument:
    try:
        data = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_unique_keys)
    except json.JSONDecodeError as error:
        raise DataValidationError(f"JSON 格式有误：第 {error.lineno} 行，第 {error.colno} 列") from error
    if not isinstance(data, dict):
        raise DataValidationError("小说 JSON 的根节点必须是对象")
    return document_from_dict(data)


def document_to_json(document: NovelDocument) -> str:
    return json.dumps(document_to_dict(document), ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def read_document(path: str | Path) -> NovelDocument:
    """只读打开 UTF-8 小说文档，兼容带 BOM 的编辑器保存结果。"""
    return document_from_json(Path(path).read_text(encoding="utf-8-sig"))
