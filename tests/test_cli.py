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
        output = StringIO()

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
                    with patch("webbrowser.open", return_value=True):
                        with redirect_stdout(output):
                            main()

            self.assertTrue((root / "edits").is_dir())

        text = output.getvalue()
        self.assertIn("Project:", text)
        self.assertIn("Opening editor:", text)


if __name__ == "__main__":
    unittest.main()
