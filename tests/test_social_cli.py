from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.project import VideoProject
from videotools.social import INSTAGRAM_REEL_STORY
from videotools.social_cli import (
    choose_framing,
    choose_social_preset,
    choose_source_render,
    print_no_renders_message,
    run_social_workflow,
)


class SocialCliHelperTests(unittest.TestCase):
    def test_choose_source_render_selects_by_number(self):
        selected = choose_source_render(
            [Path("one.mp4"), Path("two.mp4")],
            input_func=lambda prompt: "2",
            output_func=lambda message: None,
        )

        self.assertEqual(selected, Path("two.mp4"))

    def test_choose_source_render_retries_invalid_values(self):
        answers = iter(("hello", "10", "1"))
        messages = []

        selected = choose_source_render(
            [Path("one.mp4"), Path("two.mp4")],
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(selected, Path("one.mp4"))
        self.assertIn("Please enter a render number or q to cancel.", messages)
        self.assertIn("Choose a number from 1 to 2.", messages)

    def test_choose_source_render_can_cancel(self):
        messages = []

        selected = choose_source_render(
            [Path("one.mp4")],
            input_func=lambda prompt: "q",
            output_func=messages.append,
        )

        self.assertIsNone(selected)
        self.assertIn("Social export cancelled.", messages)

    def test_choose_social_preset_defaults_to_instagram(self):
        selected = choose_social_preset(
            input_func=lambda prompt: "",
            output_func=lambda message: None,
        )

        self.assertEqual(selected, INSTAGRAM_REEL_STORY)

    def test_choose_social_preset_retries_invalid_value(self):
        answers = iter(("x", "1"))
        messages = []

        selected = choose_social_preset(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(selected, INSTAGRAM_REEL_STORY)
        self.assertIn("Please choose 1 or q to cancel.", messages)

    def test_choose_social_preset_can_cancel(self):
        selected = choose_social_preset(
            input_func=lambda prompt: "quit",
            output_func=lambda message: None,
        )

        self.assertIsNone(selected)

    def test_choose_framing_defaults_to_crop(self):
        self.assertEqual(
            choose_framing(
                input_func=lambda prompt: "",
                output_func=lambda message: None,
            ),
            "crop",
        )

    def test_choose_framing_accepts_fit(self):
        self.assertEqual(
            choose_framing(
                input_func=lambda prompt: "2",
                output_func=lambda message: None,
            ),
            "fit",
        )

    def test_choose_framing_retries_invalid_value(self):
        answers = iter(("bad", "1"))
        messages = []

        selected = choose_framing(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(selected, "crop")
        self.assertIn("Please choose 1, 2, or q to cancel.", messages)

    def test_choose_framing_can_cancel(self):
        selected = choose_framing(
            input_func=lambda prompt: "q",
            output_func=lambda message: None,
        )

        self.assertIsNone(selected)


class SocialCliWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips").mkdir()
        (self.root / "exports").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "social-project"

[paths]
clips = "clips"
exports = "exports"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @patch("videotools.social_cli.list_render_files", return_value=[])
    def test_run_social_workflow_prints_message_when_no_renders(self, list_render_files_mock):
        del list_render_files_mock
        messages = []

        result = run_social_workflow(
            self.project,
            input_func=lambda prompt: "",
            output_func=messages.append,
        )

        self.assertIsNone(result)
        self.assertIn("No rendered videos found.", messages)
        self.assertIn("  video-tools render", messages)

    @patch("videotools.social_cli.convert_social_video")
    @patch("videotools.social_cli.list_render_files")
    def test_run_social_workflow_converts_selected_render(
        self,
        list_render_files_mock,
        convert_social_video_mock,
    ):
        source = self.project.exports_dir / "20260913_105103_accurate.mp4"
        source.write_bytes(b"source")
        list_render_files_mock.return_value = [source]

        output = self.project.exports_social_dir / "20260913_105103_accurate_instagram.mp4"
        convert_social_video_mock.return_value = output
        answers = iter(("1", "", ""))
        messages = []

        result = run_social_workflow(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(result, output)
        self.assertTrue(self.project.exports_social_dir.is_dir())
        convert_social_video_mock.assert_called_once()
        self.assertEqual(convert_social_video_mock.call_args.kwargs["source"], source)
        self.assertEqual(convert_social_video_mock.call_args.kwargs["preset"], INSTAGRAM_REEL_STORY)
        self.assertEqual(convert_social_video_mock.call_args.kwargs["framing"], "crop")
        self.assertIn("Social export:", messages)
        self.assertIn("Converting...", messages)


if __name__ == "__main__":
    unittest.main()
