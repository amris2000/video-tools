from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.cli import main
from videotools.edit import EditClip, EditTimeline, EditValidationError
from videotools.project import VideoProject
from videotools.render_cli import (
    choose_edit_file,
    choose_render_mode,
    print_no_edits_message,
    run_render_workflow,
)


class RenderCliHelperTests(unittest.TestCase):
    def test_choose_render_mode_defaults_to_accurate(self):
        messages = []
        mode = choose_render_mode(
            input_func=lambda prompt: "",
            output_func=messages.append,
        )

        self.assertEqual(mode, "accurate")
        self.assertTrue(any("Render mode:" in message for message in messages))

    def test_choose_render_mode_accepts_fast(self):
        self.assertEqual(
            choose_render_mode(
                input_func=lambda prompt: "2",
                output_func=lambda message: None,
            ),
            "fast",
        )

    def test_choose_render_mode_retries_after_invalid_input(self):
        answers = iter(("4", "1"))
        messages = []

        mode = choose_render_mode(
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(mode, "accurate")
        self.assertTrue(any("Please choose 1 or 2." == message for message in messages))

    def test_choose_render_mode_can_cancel(self):
        messages = []
        mode = choose_render_mode(
            input_func=lambda prompt: "q",
            output_func=messages.append,
        )

        self.assertIsNone(mode)
        self.assertIn("Render cancelled.", messages)

    def test_choose_edit_file_selects_by_number(self):
        edit_files = [Path("one.json"), Path("two.json")]

        selected = choose_edit_file(
            edit_files,
            input_func=lambda prompt: "2",
            output_func=lambda message: None,
        )

        self.assertEqual(selected, Path("two.json"))

    def test_choose_edit_file_retries_invalid_values(self):
        edit_files = [Path("one.json"), Path("two.json")]
        answers = iter(("hello", "10", "1"))
        messages = []

        selected = choose_edit_file(
            edit_files,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(selected, Path("one.json"))
        self.assertIn("Please enter an edit number or q to cancel.", messages)
        self.assertIn("Choose a number from 1 to 2.", messages)

    def test_choose_edit_file_can_cancel(self):
        messages = []
        selected = choose_edit_file(
            [Path("one.json")],
            input_func=lambda prompt: "quit",
            output_func=messages.append,
        )

        self.assertIsNone(selected)
        self.assertIn("Render cancelled.", messages)

    def test_choose_edit_file_displays_clip_counts(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "one.json"
            second = root / "two.json"
            first.write_text(
                """{
  \"version\": 1,
  \"output\": \"one_video.mp4\",
  \"clips\": []
}\n""",
                encoding="utf-8",
            )
            second.write_text(
                """{
  \"version\": 1,
  \"output\": \"two_video.mp4\",
  \"clips\": [
    {\"file\": \"day-one/clip.mp4\", \"start\": 0.0, \"end\": 2.0}
  ]
}\n""",
                encoding="utf-8",
            )

            messages = []
            selected = choose_edit_file(
                [first, second],
                input_func=lambda prompt: "2",
                output_func=messages.append,
            )

            self.assertEqual(selected, second)
            joined = "\n".join(messages)
            self.assertIn("one.json (0 clips)", joined)
            self.assertIn("two.json (1 clip)", joined)


class RenderWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips").mkdir()
        (self.root / "exports").mkdir()
        (self.root / "edits").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "render-project"

[paths]
clips = "clips"
edits = "edits"
exports = "exports"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)
        self.timeline = EditTimeline(
            output=self.project.exports_dir / "stored-output.mp4",
            clips=(EditClip(self.project.clips_dir / "clip.mp4", 0.0, 3.0),),
            version=1,
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_print_no_edits_message_is_helpful(self):
        messages = []
        print_no_edits_message(self.project, output_func=messages.append)
        joined = "\n".join(messages)
        self.assertIn(str(self.project.edits_dir), joined)
        self.assertIn("video-tools editor", joined)
        self.assertIn("video-tools sample-edit", joined)
        self.assertIn("video-tools select-edit", joined)

    @patch("videotools.render_cli.render_accurate")
    @patch("videotools.render_cli.create_render_output_path")
    @patch("videotools.render_cli.load_edit_timeline")
    @patch("videotools.render_cli.list_edit_files")
    def test_run_render_workflow_uses_output_from_edit_timeline_when_present(
        self,
        list_edit_files_mock,
        load_edit_timeline_mock,
        create_render_output_path_mock,
        render_accurate_mock,
    ):
        edit_file = self.project.edits_dir / "chosen_edit.json"
        output_path = self.project.exports_dir / "20260913_105103_accurate.mp4"
        list_edit_files_mock.return_value = [edit_file]
        load_edit_timeline_mock.return_value = self.timeline
        create_render_output_path_mock.return_value = output_path
        render_accurate_mock.return_value = output_path
        messages = []
        answers = iter(("", "1"))

        result = run_render_workflow(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertEqual(result, output_path)
        load_edit_timeline_mock.assert_called_once_with(edit_file, self.project)
        create_render_output_path_mock.assert_not_called()
        render_timeline = render_accurate_mock.call_args.args[0]
        self.assertEqual(render_timeline.output, self.timeline.output)
        self.assertEqual(render_timeline.clips, self.timeline.clips)
        self.assertEqual(render_timeline.version, self.timeline.version)
        self.assertEqual(self.timeline.output, self.project.exports_dir / "stored-output.mp4")
        self.assertEqual(render_accurate_mock.call_args.kwargs["overwrite"], False)
        joined = "\n".join(messages)
        self.assertIn("Edit: edits/chosen_edit.json", joined)
        self.assertIn("Mode: accurate", joined)
        self.assertIn("Output: exports/stored-output.mp4", joined)

    @patch("videotools.render_cli.render_fast")
    @patch("videotools.render_cli.create_render_output_path")
    @patch("videotools.render_cli.load_edit_timeline")
    @patch("videotools.render_cli.list_edit_files")
    def test_run_render_workflow_uses_fast_renderer(
        self,
        list_edit_files_mock,
        load_edit_timeline_mock,
        create_render_output_path_mock,
        render_fast_mock,
    ):
        edit_file = self.project.edits_dir / "chosen_edit.json"
        output_path = self.project.exports_dir / "20260913_105225_fast.mp4"
        list_edit_files_mock.return_value = [edit_file]
        load_edit_timeline_mock.return_value = self.timeline
        create_render_output_path_mock.return_value = output_path
        render_fast_mock.return_value = output_path
        answers = iter(("2", "1"))

        result = run_render_workflow(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=lambda message: None,
        )

        self.assertEqual(result, output_path)
        render_fast_mock.assert_called_once()
        create_render_output_path_mock.assert_not_called()
        self.assertEqual(render_fast_mock.call_args.kwargs["overwrite"], False)

    @patch("videotools.render_cli.render_accurate")
    @patch("videotools.render_cli.parse_edit_timeline")
    @patch("videotools.render_cli.read_edit_document")
    @patch("videotools.render_cli.create_render_output_path")
    @patch("videotools.render_cli.load_edit_timeline")
    @patch("videotools.render_cli.list_edit_files")
    def test_run_render_workflow_uses_timestamped_default_when_output_missing(
        self,
        list_edit_files_mock,
        load_edit_timeline_mock,
        create_render_output_path_mock,
        read_edit_document_mock,
        parse_edit_timeline_mock,
        render_accurate_mock,
    ):
        edit_file = self.project.edits_dir / "chosen_edit.json"
        fallback_output = self.project.exports_dir / "20260913_105103_accurate.mp4"
        fallback_timeline = EditTimeline(
            output=fallback_output,
            clips=self.timeline.clips,
            version=1,
        )
        list_edit_files_mock.return_value = [edit_file]
        load_edit_timeline_mock.side_effect = EditValidationError("output must be a non-empty string.")
        create_render_output_path_mock.return_value = fallback_output
        read_edit_document_mock.return_value = {
            "version": 1,
            "clips": [{"file": "clip.mp4", "start": 0.0, "end": 3.0}],
        }
        parse_edit_timeline_mock.return_value = fallback_timeline
        render_accurate_mock.return_value = fallback_output
        answers = iter(("", "1"))

        result = run_render_workflow(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=lambda message: None,
        )

        self.assertEqual(result, fallback_output)
        create_render_output_path_mock.assert_called_once_with(self.project, "accurate")
        self.assertEqual(
            read_edit_document_mock.return_value["output"],
            "20260913_105103_accurate.mp4",
        )
        parse_edit_timeline_mock.assert_called_once_with(read_edit_document_mock.return_value, self.project)

    @patch("videotools.render_cli.render_accurate")
    @patch("videotools.render_cli.list_edit_files", return_value=[])
    def test_run_render_workflow_shows_empty_edits_message_and_does_not_render(
        self,
        list_edit_files_mock,
        render_accurate_mock,
    ):
        del list_edit_files_mock
        messages = []

        result = run_render_workflow(
            self.project,
            input_func=lambda prompt: "",
            output_func=messages.append,
        )

        self.assertIsNone(result)
        render_accurate_mock.assert_not_called()
        self.assertTrue(any("No edit files found in:" in message for message in messages))

    @patch("videotools.render_cli.list_edit_files")
    def test_run_render_workflow_can_cancel_at_edit_selection(self, list_edit_files_mock):
        list_edit_files_mock.return_value = [self.project.edits_dir / "chosen_edit.json"]
        answers = iter(("", "q"))
        messages = []

        result = run_render_workflow(
            self.project,
            input_func=lambda prompt: next(answers),
            output_func=messages.append,
        )

        self.assertIsNone(result)
        self.assertIn("Render cancelled.", messages)


class RenderCliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips").mkdir()
        (self.root / "exports").mkdir()
        (self.root / "edits").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "render-project"

[paths]
clips = "clips"
edits = "edits"
exports = "exports"
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_cli_render_invokes_interactive_workflow(self):
        with patch("sys.argv", ["video-tools", "render"]):
            with patch("pathlib.Path.cwd", return_value=self.root):
                with patch("videotools.cli.run_render_workflow") as run_render_workflow_mock:
                    with redirect_stdout(StringIO()):
                        main()

        run_render_workflow_mock.assert_called_once()
        self.assertEqual(run_render_workflow_mock.call_args.args[0].root, self.root)

    def test_cli_render_reports_validation_errors(self):
        output = StringIO()

        with patch("sys.argv", ["video-tools", "render"]):
            with patch("pathlib.Path.cwd", return_value=self.root):
                with patch(
                    "videotools.cli.run_render_workflow",
                    side_effect=EditValidationError("bad"),
                ):
                    with self.assertRaises(SystemExit):
                        with redirect_stderr(output):
                            main()

        self.assertIn("ERROR: bad", output.getvalue())


if __name__ == "__main__":
    unittest.main()