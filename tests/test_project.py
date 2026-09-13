from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from videotools.edit_files import ensure_edits_dir
from videotools.init_project import create_project
from videotools.project import VideoProject


class VideoProjectTests(unittest.TestCase):
    def test_create_project_builds_edits_and_social_directories(self):
        with TemporaryDirectory() as directory:
            parent = Path(directory)

            project_root = create_project("demo", parent=parent)
            project = VideoProject.load(project_root)

            self.assertEqual(project.edits_dir, project_root / "edits")
            self.assertTrue(project.edits_dir.is_dir())
            self.assertEqual(project.exports_social_dir, project_root / "exports-social")
            self.assertTrue(project.exports_social_dir.is_dir())

    def test_legacy_project_defaults_edits_dir_and_can_create_it(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "clips").mkdir()
            (root / "exports").mkdir()
            (root / "project.toml").write_text(
                """\
name = "legacy-project"

[paths]
clips = "clips"
exports = "exports"
""",
                encoding="utf-8",
            )

            project = VideoProject.load(root)

            self.assertEqual(project.edits_dir, root / "edits")
            self.assertEqual(project.exports_social_dir, root / "exports-social")
            self.assertFalse(project.edits_dir.exists())
            self.assertFalse(project.exports_social_dir.exists())
            self.assertEqual(ensure_edits_dir(project), root / "edits")
            self.assertTrue(project.edits_dir.is_dir())


if __name__ == "__main__":
    unittest.main()