"""完整离线业务流程：真实磁盘、版本恢复、确认保护、密钥隔离。"""

from importlib import import_module, util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from novel_writer.storage.sqlite_repository import SQLiteRepository


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(util.find_spec("novel_writer.application.service"), "离线业务入口尚未实现")
        module = import_module("novel_writer.application.service")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "novels.sqlite3"
        self.service_type = module.NovelService
        self.service = module.NovelService(SQLiteRepository(self.path))
        self.state = self.service.create(title="新小说", author="作者")
        self.project_id = self.state["document"]["project"]["id"]

    def submit(self, action, **fields):
        self.state = self.service.execute(self.project_id, action, fields, expected_revision=self.state["revision"])
        return self.state

    def add_chapter(self):
        self.submit("add_chapter", title="第一章")
        return self.state["document"]["chapters"][0]["id"]

    def test_creation_immediately_persists_project(self):
        reopened = self.service_type(SQLiteRepository(self.path))
        self.assertEqual(reopened.get(self.project_id), self.state)
        self.assertEqual(reopened.list_projects()[0]["title"], "新小说")

    def test_all_manual_modules_survive_reopening(self):
        self.submit("save_project", title="改过的书名", summary="小说简介")
        self.submit("save_book_outline", theme="信任", main_plot="全书主线", ending="圆满结局")
        self.submit("add_character", name="林舟", role="主角", personality="谨慎", background="修船师")
        character_id = self.state["document"]["characters"][0]["id"]
        self.submit("save_character", character_id=character_id, name="林舟", personality="勇敢")
        self.submit("save_worldbuilding", content="雾港世界设定")
        self.submit("save_writing_rules", content="第三人称，避免重复描写")
        chapter_id = self.add_chapter()
        self.submit("save_idea", chapter_id=chapter_id, content="信从何而来？")
        self.submit("save_chapter_outline", chapter_id=chapter_id, core_idea="收到来信", objective="引出悬念", story_time="第一天")
        self.submit("save_chapter", chapter_id=chapter_id, title="潮声中的信", content="正文第一段。\n\n正文第二段。", status="draft")
        self.assertEqual(self.service_type(SQLiteRepository(self.path)).get(self.project_id), self.state)
        self.assertEqual(self.state["document"]["chapters"][0]["content"], "正文第一段。\n\n正文第二段。")
        self.assertEqual(self.state["ideas"][chapter_id], "信从何而来？")

    def test_two_body_saves_preserve_previous_text_and_increment_versions(self):
        chapter_id = self.add_chapter()
        self.submit("save_chapter", chapter_id=chapter_id, content="旧正文")
        self.submit("save_chapter", chapter_id=chapter_id, content="新正文")
        versions = [v for v in self.state["document"]["versions"] if v["entity_id"] == chapter_id]
        self.assertEqual([v["version_number"] for v in versions], [1, 2, 3])
        self.assertEqual(versions[1]["snapshot"]["content"], "旧正文")
        self.assertEqual(versions[2]["snapshot"]["content"], "新正文")

    def test_restore_adds_version_without_destroying_intermediate_history(self):
        chapter_id = self.add_chapter()
        self.submit("save_chapter", chapter_id=chapter_id, content="想恢复的内容")
        old_version = self.state["document"]["chapters"][0]["current_version_id"]
        self.submit("save_chapter", chapter_id=chapter_id, content="后来的内容")
        before = self.state["document"]["versions"]
        self.submit("restore_chapter", chapter_id=chapter_id, version_id=old_version)
        self.assertEqual(self.state["document"]["chapters"][0]["content"], "想恢复的内容")
        self.assertEqual(self.state["document"]["versions"][:-1], before)
        self.assertEqual(self.state["document"]["versions"][-1]["version_number"], 4)

    def test_confirmed_chapter_requires_explicit_authorization_to_change(self):
        chapter_id = self.add_chapter()
        self.submit("save_chapter", chapter_id=chapter_id, content="确认的内容", status="confirmed")
        saved = self.state
        with self.assertRaisesRegex(ValueError, "确认"):
            self.submit("save_chapter", chapter_id=chapter_id, content="不能擅自替换")
        self.assertEqual(self.service.get(self.project_id), saved)
        self.submit("save_chapter", chapter_id=chapter_id, content="作者同意的修改", authorize_confirmed=True)
        self.assertEqual(self.state["document"]["chapters"][0]["content"], "作者同意的修改")

    def test_confirmed_chapter_requires_authorization_for_restore(self):
        chapter_id = self.add_chapter()
        version_id = self.state["document"]["chapters"][0]["current_version_id"]
        self.submit("save_chapter", chapter_id=chapter_id, content="正式正文", status="confirmed")
        with self.assertRaisesRegex(ValueError, "确认"):
            self.submit("restore_chapter", chapter_id=chapter_id, version_id=version_id)

    def test_restore_cannot_use_version_from_another_chapter(self):
        chapter_id = self.add_chapter()
        version_id = self.state["document"]["chapters"][0]["current_version_id"]
        self.submit("add_chapter", title="第二章")
        other_id = self.state["document"]["chapters"][1]["id"]
        with self.assertRaisesRegex(ValueError, "不属于"):
            self.submit("restore_chapter", chapter_id=other_id, version_id=version_id)

    def test_missing_or_wrong_typed_text_leaves_disk_unchanged(self):
        saved = self.state
        for value in ("   ", None, 123):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.submit("save_project", title=value)
        self.assertEqual(self.service.get(self.project_id), saved)

    def test_idea_must_belong_to_existing_chapter(self):
        with self.assertRaises(ValueError):
            self.submit("save_idea", chapter_id="unknown-chapter", content="不可保存")

    def test_stale_revision_is_rejected_without_overwriting(self):
        stale_revision = self.state["revision"]
        self.submit("save_worldbuilding", content="新内容")
        with self.assertRaisesRegex(ValueError, "更新"):
            self.service.execute(self.project_id, "save_worldbuilding", {"content": "旧内容"}, expected_revision=stale_revision)
        self.assertEqual(self.service.get(self.project_id)["worldbuilding"], "新内容")

    def test_model_actions_stay_disabled_even_when_keys_exist(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "private-test-value", "GEMINI_API_KEY": "another-private-value"}):
            for action in ("generate_body", "deepseek_review", "gemini_revision", "auto_update_outline"):
                with self.subTest(action=action), self.assertRaisesRegex(ValueError, "未启用"):
                    self.submit(action)
            safe = self.service.settings()
            self.assertFalse(safe["model_calls_enabled"])
            self.assertTrue(safe["providers"]["deepseek"]["key_configured"])
            self.assertNotIn("private", str(safe))

    def test_all_eighteen_modules_are_visible_with_real_statuses(self):
        modules = self.service.modules()
        self.assertEqual(len(modules), 18)
        self.assertEqual(len({item["id"] for item in modules}), 18)
        self.assertTrue(any(item["id"] == "database" and item["status"] == "ready" for item in modules))
        self.assertTrue(any(item["id"] == "generation" and item["status"] == "planned" for item in modules))

    def test_invalid_action_or_project_identifier_has_validation_error(self):
        for action, project_id in (([], self.project_id), ({}, self.project_id), ("save_project", [])):
            with self.subTest(action=action, project_id=project_id):
                with self.assertRaises(ValueError):
                    self.service.execute(project_id, action, {}, expected_revision=self.state["revision"])


if __name__ == "__main__":
    unittest.main()
