from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.edit_files import (
    create_edit_document,
    create_empty_edit_document,
    create_new_edit_file,
    create_render_output_path,
    list_edit_files,
    output_name_for_edit_filename,
    save_edit_document,
    validate_edit_filename,
)
from videotools.project import VideoProject


class EditFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips").mkdir()
        (self.root / "exports").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "test-project"

[paths]
clips = "clips"
exports = "exports"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_create_new_edit_file_uses_timestamped_name_in_edits_dir(self):
        with patch("videotools.edit_files.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 13, 9, 21, 45)

            edit_file, output_name = create_new_edit_file(self.project)

        self.assertEqual(edit_file, self.root / "edits" / "20260913_092145_edit.json")
        self.assertEqual(output_name, "20260913_092145_video.mp4")
        self.assertTrue(self.project.edits_dir.is_dir())

    def test_create_new_edit_file_avoids_timestamp_collisions(self):
        self.project.edits_dir.mkdir(parents=True, exist_ok=True)
        (self.project.edits_dir / "20260913_092145_edit.json").write_text(
            "{}",
            encoding="utf-8",
        )

        with patch("videotools.edit_files.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 13, 9, 21, 45)

            edit_file, output_name = create_new_edit_file(self.project)

        self.assertEqual(edit_file, self.root / "edits" / "20260913_092145_2_edit.json")
        self.assertEqual(output_name, "20260913_092145_2_video.mp4")

    def test_list_edit_files_filters_json_and_sorts_newest_first(self):
        self.project.edits_dir.mkdir(parents=True, exist_ok=True)
        oldest = self.project.edits_dir / "20260913_092145_edit.json"
        newest = self.project.edits_dir / "20260913_101422_edit.json"
        ignored = self.project.edits_dir / "notes.txt"
        nested_dir = self.project.edits_dir / "nested"

        oldest.write_text("{}", encoding="utf-8")
        newest.write_text("{}", encoding="utf-8")
        ignored.write_text("ignore", encoding="utf-8")
        nested_dir.mkdir()
        (nested_dir / "20260913_111111_edit.json").write_text("{}", encoding="utf-8")

        self.assertEqual(list_edit_files(self.project), [newest, oldest])

    def test_validate_edit_filename_rejects_directory_separators(self):
        with self.assertRaisesRegex(ValueError, "directory separators"):
            validate_edit_filename("nested/edit.json")

        with self.assertRaisesRegex(ValueError, "directory separators"):
            validate_edit_filename("nested\\edit.json")

    def test_output_name_for_edit_filename_reuses_edit_stem(self):
        self.assertEqual(
            output_name_for_edit_filename("morning-ride_edit.json"),
            "morning-ride_video.mp4",
        )

    def test_save_edit_document_replaces_file_contents(self):
        document = create_empty_edit_document("draft_edit.json", "draft_video.mp4")
        create_edit_document(self.project, "draft_edit.json", document)

        updated = {
            "version": 1,
            "output": "updated_video.mp4",
            "clips": [],
        }
        save_edit_document(self.project, "draft_edit.json", updated)

        text = (self.project.edits_dir / "draft_edit.json").read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), updated)

    def test_create_render_output_path_uses_mode_and_exports_dir(self):
        with patch("videotools.edit_files.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 13, 10, 51, 3)

            output_path = create_render_output_path(self.project, "accurate")

        self.assertEqual(
            output_path,
            self.root / "exports" / "20260913_105103_accurate.mp4",
        )

    def test_create_render_output_path_avoids_collisions(self):
        self.project.exports_dir.mkdir(parents=True, exist_ok=True)
        (self.project.exports_dir / "20260913_105103_fast.mp4").write_text("old", encoding="utf-8")

        with patch("videotools.edit_files.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 13, 10, 51, 3)

            output_path = create_render_output_path(self.project, "fast")

        self.assertEqual(
            output_path,
            self.root / "exports" / "20260913_105103_fast_2.mp4",
        )


if __name__ == "__main__":
    unittest.main()