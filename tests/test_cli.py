from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from videotools.cli import main


class CliHelpTests(unittest.TestCase):
    def test_help_lists_commands_without_requiring_a_project(self):
        output = StringIO()

        with TemporaryDirectory() as directory:
            with patch("sys.argv", ["video-tools", "help"]):
                with patch("pathlib.Path.cwd", return_value=Path(directory)):
                    with redirect_stdout(output):
                        main()

        text = output.getvalue()
        self.assertIn("render", text)
        self.assertIn("sample-edit", text)
        self.assertIn("select-edit", text)
        self.assertIn("journal", text)
        self.assertIn("video-tools journal add", text)
        self.assertIn("video-tools journal list", text)

    def test_editor_command_requires_project_and_prepares_edits_dir(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clips").mkdir()
            (root / "exports").mkdir()
            (root / "project.toml").write_text(
                """\
name = "cli-project"

[paths]
clips = "clips"
exports = "exports"
""",
                encoding="utf-8",
            )

            with patch("sys.argv", ["video-tools", "editor"]):
                with patch("pathlib.Path.cwd", return_value=root):
                    with patch("videotools.cli.run_editor_server") as run_editor:
                        with redirect_stdout(StringIO()):
                            main()

            self.assertTrue((root / "edits").is_dir())
            run_editor.assert_called_once()
            self.assertEqual(run_editor.call_args.args[0].root, root)

    def test_render_help_describes_interactive_workflow_without_overwrite(self):
        output = StringIO()

        with patch("sys.argv", ["video-tools", "render", "--help"]):
            with self.assertRaises(SystemExit):
                with redirect_stdout(output):
                    main()

        text = output.getvalue()
        self.assertIn("Interactively choose a render mode", text)
        self.assertIn("YYYYMMDD_HHMMSS_accurate.mp4", text)
        self.assertNotIn("--overwrite", text)
        self.assertNotIn("--mode", text)



if __name__ == "__main__":
    unittest.main()
