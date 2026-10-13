"""验证内容关联与版本记录的真实数据约束，不调用网络或写入小说。"""

from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from novel_writer.domain.models import DataValidationError, validate_document
from novel_writer.storage.json_codec import document_from_dict, document_from_json, document_to_json


class NovelDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(
            (PROJECT_ROOT / "examples" / "sample-novel" / "novel.json").read_text(encoding="utf-8")
        )

    def assert_invalid(self, message: str) -> None:
        with self.assertRaisesRegex(DataValidationError, message):
            document_from_dict(self.data)

    def test_full_sample_round_trip_preserves_chinese_and_history(self) -> None:
        document = document_from_dict(self.data)
        encoded = document_to_json(document)
        self.assertIn("雾港来信", encoded)
        self.assertEqual(document_from_json(encoded), document)
        self.assertNotEqual(document.versions[0].snapshot["content"], document.versions[1].snapshot["content"])

    def test_new_project_can_start_without_chapters_or_outline(self) -> None:
        document = document_from_dict({"schema_version": 1, "project": {"title": "新小说"}})
        self.assertIsNone(document.book_outline)
        self.assertEqual(document.chapters, [])
        self.assertTrue(document.project.id)

    def test_renaming_and_reordering_keep_id_references(self) -> None:
        self.data["chapters"][0]["title"] = "新的章节标题"
        self.data["chapters"][0]["number"] = 5
        self.data["characters"][0]["name"] = "新的名字"
        document = document_from_dict(self.data)
        self.assertEqual(document.chapter_outlines[0].chapter_id, document.chapters[0].id)
        self.assertEqual(document.characters[1].relationships[0].target_character_id, document.characters[0].id)
        self.assertEqual(document.versions[0].snapshot["number"], 1)

    def test_editing_current_content_leaves_old_snapshots_unchanged(self) -> None:
        document = document_from_dict(self.data)
        snapshots = deepcopy([item.snapshot for item in document.versions])
        document.chapters[0].content = "尚未保存的新草稿。"
        self.assertEqual([item.snapshot for item in document.versions], snapshots)

    def test_missing_schema_version_is_rejected(self) -> None:
        del self.data["schema_version"]
        self.assert_invalid("schema_version")

    def test_future_schema_version_is_rejected(self) -> None:
        self.data["schema_version"] = 2
        self.assert_invalid("schema_version")

    def test_unknown_fields_are_rejected_instead_of_silently_lost(self) -> None:
        for container in (self.data, self.data["chapters"][0], self.data["book_outline"]["volumes"][0]):
            with self.subTest(container=container):
                container["unexpected_field"] = "不能静默忽略"
                self.assert_invalid("字段或结构")
                del container["unexpected_field"]

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "重复字段"):
            document_from_json('{"schema_version": 1, "schema_version": 2}')

    def test_collections_cannot_silently_accept_empty_string_or_object(self) -> None:
        for field_name in ("characters", "chapters", "chapter_outlines", "versions"):
            original = self.data[field_name]
            for wrong_value in ("", {}, None):
                with self.subTest(field=field_name, value=wrong_value):
                    self.data[field_name] = wrong_value
                    self.assert_invalid("必须是列表")
            self.data[field_name] = original

    def test_nested_collections_require_lists(self) -> None:
        for container, field_name in (
            (self.data["book_outline"], "volumes"),
            (self.data["characters"][0], "relationships"),
            (self.data["chapter_outlines"][0], "scenes"),
        ):
            with self.subTest(field=field_name):
                original = container[field_name]
                container[field_name] = {}
                self.assert_invalid("必须是列表")
                container[field_name] = original

    def test_json_nan_is_rejected(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "不允许"):
            document_from_json('{"value": NaN}')

    def test_invalid_json_reports_location(self) -> None:
        with self.assertRaisesRegex(DataValidationError, "第.*行"):
            document_from_json('{"schema_version":')

    def test_duplicate_record_ids_are_rejected(self) -> None:
        self.data["characters"][1]["id"] = self.data["characters"][0]["id"]
        self.assert_invalid("ID 不能重复")

    def test_cross_project_content_is_rejected(self) -> None:
        self.data["chapters"][0]["project_id"] = "other-project"
        self.assert_invalid("不属于当前小说")

    def test_missing_character_in_scene_is_rejected(self) -> None:
        self.data["chapter_outlines"][0]["scenes"][0]["character_ids"] = ["missing-person"]
        self.assert_invalid("不存在的人物")

    def test_missing_chapter_in_outline_is_rejected(self) -> None:
        self.data["chapter_outlines"][0]["chapter_id"] = "missing-chapter"
        self.assert_invalid("不存在的章节")

    def test_missing_character_in_relationship_is_rejected(self) -> None:
        self.data["characters"][0]["relationships"][0]["target_character_id"] = "missing-person"
        self.assert_invalid("不存在的人物")

    def test_chapter_cannot_be_assigned_to_two_volumes(self) -> None:
        second = deepcopy(self.data["book_outline"]["volumes"][0])
        second["number"] = 2
        self.data["book_outline"]["volumes"].append(second)
        self.assert_invalid("重复分配")

    def test_duplicate_chapter_order_is_rejected(self) -> None:
        second = deepcopy(self.data["chapters"][0])
        second.update(id="demo-chapter-2", status="draft", current_version_id=None)
        self.data["chapters"].append(second)
        self.assert_invalid("章节顺序不能重复")

    def test_chapter_number_requires_positive_integer(self) -> None:
        for value in (0, -1, True, "1"):
            with self.subTest(value=value):
                self.data["chapters"][0]["number"] = value
                with self.assertRaises(DataValidationError):
                    document_from_dict(self.data)

    def test_invalid_status_is_rejected(self) -> None:
        self.data["chapters"][0]["status"] = "published-by-ai"
        self.assert_invalid("必须是")

    def test_time_requires_utc_timezone(self) -> None:
        for value in ("2026-10-13T02:00:00", "2026-10-13T10:00:00+08:00"):
            with self.subTest(value=value):
                self.data["project"]["created_at"] = value
                self.assert_invalid("UTC 时区")

    def test_updated_time_cannot_precede_created_time(self) -> None:
        self.data["project"]["updated_at"] = "2026-10-12T02:00:00+00:00"
        self.assert_invalid("更新时间不能早于")

    def test_missing_current_version_is_rejected(self) -> None:
        self.data["chapters"][0]["current_version_id"] = "missing-version"
        self.assert_invalid("当前版本不存在")

    def test_confirmed_chapter_requires_saved_version(self) -> None:
        self.data["chapters"][0]["current_version_id"] = None
        self.assert_invalid("必须关联保存版本")

    def test_version_chain_cannot_skip_a_version_number(self) -> None:
        self.data["versions"][1]["version_number"] = 3
        self.assert_invalid("逐次递增")

    def test_version_chain_cannot_reference_itself(self) -> None:
        self.data["versions"][1]["previous_version_id"] = "demo-version-2"
        self.assert_invalid("逐次递增")

    def test_version_chain_cannot_link_different_entities(self) -> None:
        document = document_from_dict(self.data)
        self.data["versions"][0].update(
            entity_type="character", entity_id=document.characters[0].id,
            snapshot=asdict(document.characters[0]),
        )
        self.assert_invalid("同一内容")

    def test_duplicate_version_number_is_rejected(self) -> None:
        self.data["versions"][1]["version_number"] = 1
        self.assert_invalid("版本号不能重复")

    def test_snapshot_requires_full_content_fields(self) -> None:
        del self.data["versions"][0]["snapshot"]["content"]
        self.assert_invalid("完整的内容字段")

    def test_snapshot_cannot_belong_to_other_entity(self) -> None:
        self.data["versions"][0]["snapshot"]["id"] = "other-chapter"
        self.assert_invalid("快照编号与目标不一致")

    def test_snapshot_save_time_cannot_precede_content_update(self) -> None:
        self.data["versions"][0]["snapshot"]["updated_at"] = "2026-10-13T02:06:00+00:00"
        self.assert_invalid("保存时间不能早于")

    def test_non_chapter_snapshot_supports_nested_data(self) -> None:
        document = document_from_dict(self.data)
        self.data["versions"].append({
            "id": "demo-outline-version", "project_id": document.project.id,
            "entity_type": "book_outline", "entity_id": document.book_outline.id,
            "version_number": 1, "snapshot": asdict(document.book_outline),
            "created_at": "2026-10-13T02:10:00+00:00",
        })
        restored = document_from_dict(self.data)
        validate_document(restored)
        self.assertEqual(len(restored.versions), 3)


if __name__ == "__main__":
    unittest.main()
