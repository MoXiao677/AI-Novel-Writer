"""本地技能资料导入：原文保留、独立存储和输入边界。"""

from contextlib import closing
from importlib import import_module, util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class SkillImportTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(util.find_spec("novel_writer.application.skill_import"), "本地 Skills 导入尚未实现")
        self.module = import_module("novel_writer.application.skill_import")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "novels.sqlite3"
        self.library = self.module.SkillLibrary(self.path)
        self.files = [{"path": "SKILL.md", "content": "---\nname: 人物检查\ndescription: 检查人物动机和行为一致性\n---\n\n# 人物检查\n保持原文。\n"}]

    def test_single_skill_persists_original_text_on_reopening(self):
        record = self.library.import_files(self.files)
        self.assertEqual(record["name"], "人物检查")
        self.assertEqual(record["description"], "检查人物动机和行为一致性")
        self.assertEqual(record["files"], self.files)
        self.assertEqual(record["primary_path"], "SKILL.md")
        self.assertTrue(record["id"])
        self.assertTrue(record["imported_at"].endswith("+00:00"))
        self.assertEqual(self.module.SkillLibrary(self.path).get(record["id"]), record)

    def test_folder_references_preserve_bom_spaces_newlines_and_html_as_text(self):
        files = [
            {"path": "人物助手/SKILL.md", "content": '\ufeff---\r\nname: "人物助手"\r\ndescription: "资料导入"\r\n---\r\n  正文  \r\n<script>alert(1)</script>\r\n'},
            {"path": "人物助手/references/规则.md", "content": "  规则\n\n尾部空格  "},
        ]
        record = self.library.import_files(files)
        self.assertEqual(record["files"], files)
        self.assertEqual(record["name"], "人物助手")
        self.assertEqual(record["description"], "资料导入")

    def test_listing_returns_metadata_without_file_text(self):
        record = self.library.import_files(self.files)
        metadata = self.library.list_skills()[0]
        self.assertEqual(metadata["id"], record["id"])
        self.assertEqual(metadata["name"], record["name"])
        self.assertNotIn("files", metadata)
        self.assertNotIn("保持原文", str(metadata))

    def test_duplicate_imports_create_independent_records(self):
        first = self.library.import_files(self.files)
        second = self.library.import_files(self.files)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.library.get(first["id"]), first)
        self.assertEqual(len(self.library.list_skills()), 2)

    def test_input_and_returned_objects_cannot_change_saved_record(self):
        record = self.library.import_files(self.files)
        self.files[0]["content"] = "输入已改"
        record["files"][0]["content"] = "返回值已改"
        self.assertIn("保持原文", self.library.get(record["id"])["files"][0]["content"])

    def test_missing_frontmatter_uses_folder_or_default_name(self):
        for path, expected in (("写作助手/SKILL.md", "写作助手"), ("SKILL.md", "未命名技能")):
            with self.subTest(path=path):
                record = self.library.import_files([{"path": path, "content": "# 原始资料\n无需元信息"}])
                self.assertEqual(record["name"], expected)
                self.assertEqual(record["description"], "")

    def test_multiline_description_is_extracted_and_long_metadata_is_bounded(self):
        record = self.library.import_files([{"path": "SKILL.md", "content": "---\nname: 示例\ndescription: >-\n  第一行\n  第二行\n---\n正文"}])
        self.assertEqual(record["description"], "第一行 第二行")
        long_text = "---\nname: " + "名" * 300 + "\ndescription: " + "述" * 3000 + "\n---\n"
        record = self.library.import_files([{"path": "SKILL.md", "content": long_text}])
        self.assertLessEqual(len(record["name"]), 200)
        self.assertLessEqual(len(record["description"]), 2000)
        self.assertEqual(record["files"][0]["content"], long_text)

    def test_requires_exactly_one_skill_entrypoint(self):
        for files in ([], [{"path": "README.md", "content": "无入口"}], [*self.files, {"path": "nested/SKILL.md", "content": "第二个入口"}]):
            with self.subTest(files=files), self.assertRaises(ValueError):
                self.library.import_files(files)
        self.assertEqual(self.library.list_skills(), [])

    def test_rejects_absolute_and_traversing_paths(self):
        invalid = ["/SKILL.md", "C:/SKILL.md", "C:SKILL.md", "../SKILL.md", "folder/../SKILL.md", "folder/./SKILL.md", "folder//SKILL.md", r"..\SKILL.md", r"folder\..\SKILL.md", r"\server\share\SKILL.md", "SKILL.md:payload.md", "bad\x00/SKILL.md"]
        for path in invalid:
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.library.import_files([{"path": path, "content": "原文"}])
        self.assertEqual(self.library.list_skills(), [])

    def test_rejects_duplicate_paths_case_insensitively(self):
        for path in ("guide.md", "GUIDE.MD"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.library.import_files([*self.files, {"path": "guide.md", "content": "first"}, {"path": path, "content": "second"}])
        self.assertEqual(self.library.list_skills(), [])

    def test_rejects_files_outside_the_selected_skill_folder(self):
        with self.assertRaises(ValueError):
            self.library.import_files([{"path": "one/SKILL.md", "content": "入口"}, {"path": "two/notes.md", "content": "别的技能"}])

    def test_rejects_scripts_and_non_markdown_without_partial_import(self):
        for path in ("run.py", "run.js", "run.sh", "README.txt", "page.html", "SKILL.md.exe"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.library.import_files([*self.files, {"path": path, "content": "不得执行"}])
        self.assertEqual(self.library.list_skills(), [])

    def test_rejects_unknown_fields_and_non_text(self):
        invalid = [None, {}, "SKILL.md", [None], [{"path": "SKILL.md"}], [{"path": "SKILL.md", "content": "", "execute": True}], [{"path": 1, "content": ""}], [{"path": "SKILL.md", "content": b"bytes"}], [{"path": "SKILL.md", "content": None}], [{"path": "SKILL.md", "content": "\ud800"}]]
        for files in invalid:
            with self.subTest(files=repr(files)), self.assertRaises(ValueError):
                self.library.import_files(files)
        self.assertEqual(self.library.list_skills(), [])

    def test_rejects_more_than_one_hundred_files(self):
        files = [*self.files, *[{"path": f"ref/{number}.md", "content": "参考"} for number in range(100)]]
        with self.assertRaises(ValueError):
            self.library.import_files(files)
        self.assertEqual(self.library.list_skills(), [])

    def test_total_limit_counts_utf8_bytes_across_files(self):
        files = [*self.files, {"path": "reference.md", "content": "中" * 700000}]
        with self.assertRaises(ValueError):
            self.library.import_files(files)
        self.assertEqual(self.library.list_skills(), [])

    def test_unknown_id_raises_key_error_and_malformed_id_is_rejected(self):
        with self.assertRaises(KeyError):
            self.library.get("missing")
        for identifier in (None, [], ""):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                self.library.get(identifier)

    def test_skills_table_does_not_modify_existing_projects_or_database_version(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute("INSERT INTO projects VALUES ('existing', 'untouched')")
            connection.execute("PRAGMA user_version = 41")
        self.module.SkillLibrary(self.path).import_files(self.files)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 41)
            self.assertEqual(connection.execute("SELECT * FROM projects").fetchall(), [("existing", "untouched")])

    def test_failed_insert_preserves_existing_imports(self):
        first = self.library.import_files(self.files)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TRIGGER fail_import BEFORE INSERT ON skills BEGIN SELECT RAISE(ABORT, 'simulated failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.library.import_files(self.files)
        self.assertEqual(self.library.get(first["id"]), first)
        self.assertEqual(len(self.library.list_skills()), 1)

    def test_connection_closes_when_initialization_fails(self):
        connection = MagicMock()
        connection.execute.side_effect = sqlite3.OperationalError("configuration failure")
        with patch("novel_writer.storage.skills_repository.sqlite3.connect", return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):
                self.module.SkillLibrary(self.path)
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
