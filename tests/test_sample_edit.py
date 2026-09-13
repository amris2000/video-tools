from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.project import VideoProject
from videotools.render import StreamSignature
from videotools.sample_edit import (
    SampleEditError,
    create_sample_edit,
    create_selected_edit,
)


class SampleEditTests(unittest.TestCase):
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

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_creates_centered_selections_from_compatible_clips(
        self,
        probe,
        which,
    ):
        del which
        first = self.add_clip("day-one/first.mp4")
        second = self.add_clip("day-one/second.mp4")
        third = self.add_clip("other-format.mp4")

        signatures = {
            first: self.signature(duration=10.0, width=3840),
            second: self.signature(duration=2.0, width=3840),
            third: self.signature(duration=10.0, width=1920),
        }
        probe.side_effect = lambda path, ffprobe: signatures[path]

        result = create_sample_edit(self.project)
        document = json.loads(result.edit_file.read_text(encoding="utf-8"))

        self.assertEqual(result.clip_count, 2)
        self.assertEqual(result.skipped_count, 1)
        self.assertEqual(result.edit_file.parent, self.project.edits_dir)
        self.assertRegex(result.edit_file.name, r"^\d{8}_\d{6}_edit\.json$")
        self.assertRegex(document["output"], r"^\d{8}_\d{6}_video\.mp4$")
        self.assertEqual(
            document["output"],
            result.edit_file.name.replace("_edit.json", "_video.mp4"),
        )
        self.assertEqual(document["clips"][0]["file"], "day-one/first.mp4")
        self.assertEqual(document["clips"][0]["start"], 3.5)
        self.assertEqual(document["clips"][0]["end"], 6.5)
        self.assertEqual(document["clips"][1]["start"], 0.0)
        self.assertEqual(document["clips"][1]["end"], 2.0)

    def test_rejects_project_without_video_clips(self):
        with self.assertRaisesRegex(SampleEditError, "No video clips"):
            create_sample_edit(self.project)

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_rejects_when_no_clip_has_a_readable_duration(self, probe, which):
        del which
        self.add_clip("clip.mp4")
        probe.return_value = self.signature(duration=None, width=3840)

        with self.assertRaisesRegex(SampleEditError, "readable durations"):
            create_sample_edit(self.project)

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_creates_unique_file_when_timestamp_collides(self, probe, which):
        del which
        self.add_clip("clip.mp4")
        probe.return_value = self.signature(duration=10.0, width=3840)
        self.project.edits_dir.mkdir(parents=True, exist_ok=True)
        existing = self.project.edits_dir / "20260913_092145_edit.json"
        existing.write_text("existing", encoding="utf-8")

        with patch("videotools.edit_files.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = datetime(2026, 9, 13, 9, 21, 45)

            result = create_sample_edit(self.project)

        self.assertEqual(
            result.edit_file,
            self.project.edits_dir / "20260913_092145_2_edit.json",
        )

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_interactive_selection_preserves_chosen_order(self, probe, which):
        del which
        first = self.add_clip("first.mp4")
        second = self.add_clip("second.mp4")
        signatures = {
            first: self.signature(duration=10.0, width=3840),
            second: self.signature(duration=8.0, width=3840),
        }
        probe.side_effect = lambda path, ffprobe: signatures[path]
        answers = iter(("2", "1", "q"))
        messages = []

        result = create_selected_edit(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )
        document = json.loads(result.edit_file.read_text(encoding="utf-8"))

        self.assertEqual(result.clip_count, 2)
        self.assertEqual(result.edit_file.parent, self.project.edits_dir)
        self.assertRegex(result.edit_file.name, r"^\d{8}_\d{6}_edit\.json$")
        self.assertRegex(document["output"], r"^\d{8}_\d{6}_video\.mp4$")
        self.assertEqual(
            document["output"],
            result.edit_file.name.replace("_edit.json", "_video.mp4"),
        )
        self.assertEqual(document["clips"][0]["file"], "second.mp4")
        self.assertEqual(document["clips"][1]["file"], "first.mp4")
        self.assertEqual(document["clips"][0]["start"], 2.5)
        self.assertTrue(any("Added second.mp4" in item for item in messages))

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_interactive_selection_rejects_incompatible_clip(self, probe, which):
        del which
        first = self.add_clip("first.mp4")
        second = self.add_clip("second.mp4")
        signatures = {
            first: self.signature(duration=10.0, width=3840),
            second: self.signature(duration=10.0, width=1920),
        }
        probe.side_effect = lambda path, ffprobe: signatures[path]
        answers = iter(("1", "2", "done"))
        messages = []

        result = create_selected_edit(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(result.clip_count, 1)
        self.assertTrue(any("Cannot add that clip" in item for item in messages))

    @patch("videotools.sample_edit.shutil.which", return_value="ffprobe")
    @patch("videotools.sample_edit.probe_stream_signature")
    def test_interactive_selection_requires_at_least_one_clip(self, probe, which):
        del which
        self.add_clip("clip.mp4")
        probe.return_value = self.signature(duration=10.0, width=3840)

        with self.assertRaisesRegex(SampleEditError, "No clips selected"):
            create_selected_edit(
                self.project,
                input_func=lambda prompt: "q",
                output_func=lambda message: None,
            )

    def add_clip(self, relative_path: str) -> Path:
        path = self.root / "clips" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    @staticmethod
    def signature(duration: float | None, width: int) -> StreamSignature:
        return StreamSignature(
            video=(
                ("codec_name", "hevc"),
                ("width", width),
                ("height", 3360),
                ("pix_fmt", "yuv420p10le"),
                ("avg_frame_rate", "30000/1001"),
            ),
            audio=(
                ("codec_name", "aac"),
                ("sample_rate", "48000"),
                ("channels", 2),
            ),
            duration=duration,
        )


if __name__ == "__main__":
    unittest.main()
