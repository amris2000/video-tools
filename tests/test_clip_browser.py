import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from videotools.project import VideoProject
from videotools.services.clips import list_clips, resolve_thumbnail
from videotools.thumbnails import thumbnail_name
from videotools.web.schemas import ClipResponse


class ClipBrowserCatalogTests(unittest.TestCase):
    def test_configured_paths_all_clips_and_partial_metadata(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "footage").mkdir()
            (root / "cache" / "thumbnails").mkdir(parents=True)
            project = VideoProject(root.resolve(), {"paths": {"clips": "footage", "metadata": "cache"}})
            first = root / "footage" / "first.MP4"
            first.touch()
            (root / "footage" / "unprobed.mp4").touch()
            thumb = root / "cache" / "thumbnails" / thumbnail_name(first, root)
            thumb.touch()
            (root / "cache" / "clip_report.json").write_text(json.dumps({"clips": [
                {"relative_path": "footage/first.MP4", "duration": 12.5, "video": {"width": 1920, "height": 1080, "fps": 30}},
                {"relative_path": "footage/deleted.mp4", "duration": 5},
                None,
            ]}))
            clips = [ClipResponse(**clip) for clip in list_clips(project, "demo")]
            self.assertEqual(len(clips), 2)
            self.assertEqual(clips[0].duration, 12.5)
            self.assertIn("/api/projects/demo/thumbnails/", clips[0].thumbnail_url)
            self.assertIsNone(clips[1].duration)
            (root / "cache" / "clip_report.json").write_text("broken")
            self.assertEqual(len(list_clips(project, "demo")), 2)
            for path in ["../secret.png", "/secret.png", "C:/secret.png", "thumbnails/file.mp4"]:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    resolve_thumbnail(project, path)

    def test_missing_clip_directory_is_empty(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(list_clips(VideoProject(Path(directory).resolve(), {}), "demo"), [])



class ClipApiTests(unittest.TestCase):
    def test_project_scoping_thumbnail_and_missing_project(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        from videotools.services.projects import load_project_info
        from videotools.web.routers.projects import get_clips, get_thumbnail
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "project.toml").write_text('name = "demo"\n')
            (root / "clips").mkdir()
            (root / "clips" / "one.mp4").touch()
            (root / "metadata" / "thumbnails").mkdir(parents=True)
            (root / "metadata" / "thumbnails" / "one.png").touch()
            info = load_project_info(root)
            with patch("videotools.web.routers.projects.get_project", return_value=info):
                self.assertEqual(get_clips("demo")[0]["path"], "clips/one.mp4")
                self.assertEqual(Path(get_thumbnail("demo", "thumbnails/one.png").path), root / "metadata" / "thumbnails" / "one.png")
                for bad in ("../secret.png", "thumbnails/missing.png"):
                    with self.assertRaises(HTTPException) as error:
                        get_thumbnail("demo", bad)
                    self.assertEqual(error.exception.status_code, 404)
            with patch("videotools.web.routers.projects.get_project", return_value=None):
                with self.assertRaises(HTTPException) as error:
                    get_clips("missing")
                self.assertEqual(error.exception.status_code, 404)
            for bad in ("..", "../demo", "C:"):
                with self.assertRaises(HTTPException):
                    get_clips(bad)


if __name__ == "__main__":
    unittest.main()
