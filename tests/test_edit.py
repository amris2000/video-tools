import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from videotools.edit import EditValidationError, load_edit_timeline
from videotools.project import VideoProject


class EditTimelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips" / "day-one").mkdir(parents=True)
        (self.root / "exports").mkdir()
        (self.root / "metadata").mkdir()
        (self.root / "clips" / "day-one" / "GX010017.MP4").touch()
        (self.root / "project.toml").write_text(
            """\
name = "test-project"

[paths]
clips = "clips"
metadata = "metadata"
exports = "exports"
journal = "journal.json"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_edit(self, value) -> Path:
        edit_file = self.root / "edit.json"
        edit_file.write_text(json.dumps(value), encoding="utf-8")
        return edit_file

    def valid_edit(self) -> dict:
        return {
            "version": 1,
            "output": "ride.mp4",
            "clips": [
                {
                    "file": "day-one/GX010017.MP4",
                    "start": 2.5,
                    "end": 7.8,
                    "label": "bike starts moving",
                }
            ],
        }

    def test_loads_valid_timeline_and_resolves_project_paths(self):
        timeline = load_edit_timeline(
            self.write_edit(self.valid_edit()),
            self.project,
        )

        self.assertEqual(timeline.version, 1)
        self.assertEqual(timeline.output, self.root / "exports" / "ride.mp4")
        self.assertEqual(
            timeline.clips[0].file,
            self.root / "clips" / "day-one" / "GX010017.MP4",
        )
        self.assertAlmostEqual(timeline.clips[0].duration, 5.3)

    def test_version_is_optional_for_version_one(self):
        value = self.valid_edit()
        del value["version"]

        timeline = load_edit_timeline(self.write_edit(value), self.project)

        self.assertEqual(timeline.version, 1)

    def test_rejects_empty_clip_list(self):
        value = self.valid_edit()
        value["clips"] = []

        with self.assertRaisesRegex(EditValidationError, "non-empty array"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_end_before_start(self):
        value = self.valid_edit()
        value["clips"][0]["end"] = 2.5

        with self.assertRaisesRegex(EditValidationError, "end must be greater"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_boolean_timestamp(self):
        value = self.valid_edit()
        value["clips"][0]["start"] = True

        with self.assertRaisesRegex(EditValidationError, "start must be a number"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_missing_source_file(self):
        value = self.valid_edit()
        value["clips"][0]["file"] = "missing.mp4"

        with self.assertRaisesRegex(EditValidationError, "does not exist"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_source_path_outside_clips(self):
        value = self.valid_edit()
        value["clips"][0]["file"] = "../outside.mp4"

        with self.assertRaisesRegex(EditValidationError, "inside.*clips"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_output_path_outside_exports(self):
        value = self.valid_edit()
        value["output"] = "../outside.mp4"

        with self.assertRaisesRegex(EditValidationError, "inside.*exports"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_rejects_future_property_with_explicit_message(self):
        value = self.valid_edit()
        value["clips"][0]["speed"] = 2.0

        with self.assertRaisesRegex(EditValidationError, "not supported in version 1"):
            load_edit_timeline(self.write_edit(value), self.project)

    def test_reports_json_location(self):
        edit_file = self.root / "edit.json"
        edit_file.write_text('{"output":', encoding="utf-8")

        with self.assertRaisesRegex(EditValidationError, "line 1, column"):
            load_edit_timeline(edit_file, self.project)


if __name__ == "__main__":
    unittest.main()
