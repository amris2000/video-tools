from http import HTTPStatus
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from videotools.editor.server import EditorRequestHandler, start_editor_server
from videotools.project import VideoProject


class EditorServerTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        (self.root / "clips" / "day-one").mkdir(parents=True)
        (self.root / "exports").mkdir()
        (self.root / "metadata").mkdir()
        (self.root / "edits").mkdir()
        (self.root / "project.toml").write_text(
            """\
name = "editor-project"

[paths]
clips = "clips"
edits = "edits"
metadata = "metadata"
exports = "exports"
""",
            encoding="utf-8",
        )

        self.clip_one = self.root / "clips" / "day-one" / "GX010017.MP4"
        self.clip_two = self.root / "clips" / "day-one" / "GX010020.MP4"
        self.clip_one.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
        self.clip_two.write_bytes(b"0123456789abcdefghijklmnopqrstuvwxyz")
        (self.root / "exports" / "20260913_111500_video.mp4").write_bytes(b"render-one-data")
        (self.root / "exports" / "20260913_101500_video.mp4").write_bytes(b"render-two-data")
        (self.root / "exports" / "ignore.txt").write_text("skip", encoding="utf-8")
        (self.root / "exports" / "nested").mkdir()
        (self.root / "exports" / "nested" / "nested.mp4").write_bytes(b"nested")

        (self.root / "metadata" / "clip_report.json").write_text(
            json.dumps(
                {
                    "summary": {"clip_count": 2},
                    "clips": [
                        {
                            "name": self.clip_one.name,
                            "relative_path": "clips/day-one/GX010017.MP4",
                            "duration": 12.5,
                        },
                        {
                            "name": self.clip_two.name,
                            "relative_path": "clips/day-one/GX010020.MP4",
                            "duration": 6.0,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

        (self.root / "edits" / "20260913_101500_edit.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "output": "20260913_101500_video.mp4",
                    "clips": [
                        {
                            "file": "day-one/GX010017.MP4",
                            "start": 1.0,
                            "end": 4.0,
                            "label": "First",
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / "edits" / "20260913_093012_edit.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "output": "20260913_093012_video.mp4",
                    "clips": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

        self.project = VideoProject.load(self.root)
        self.server = start_editor_server(self.project, preferred_port=0)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host, self.port = self.server.server_address[:2]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary_directory.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None):
        connection = HTTPConnection(self.host, self.port, timeout=5)
        payload = None
        final_headers = dict(headers or {})

        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            final_headers.setdefault("Content-Type", "application/json")
            final_headers.setdefault("Content-Length", str(len(payload)))

        connection.request(method, path, body=payload, headers=final_headers)
        response = connection.getresponse()
        data = response.read()
        connection.close()

        parsed = None
        if response.getheader("Content-Type", "").startswith("application/json"):
            parsed = json.loads(data.decode("utf-8"))

        return response.status, response, data, parsed

    def test_serves_index_and_project_info(self):
        status, response, data, parsed = self.request("GET", "/")
        del response, parsed
        self.assertEqual(status, 200)
        self.assertIn(b"Video Tools Timeline Editor", data)

        status, _, _, parsed = self.request("GET", "/api/project")
        self.assertEqual(status, 200)
        self.assertEqual(parsed["name"], "editor-project")
        self.assertEqual(parsed["root"], str(self.root))

    def test_lists_loads_and_creates_edits(self):
        status, _, _, parsed = self.request("GET", "/api/edits")
        self.assertEqual(status, 200)
        self.assertEqual(
            [item["filename"] for item in parsed["edits"]],
            ["20260913_101500_edit.json", "20260913_093012_edit.json"],
        )

        status, _, _, parsed = self.request("GET", "/api/edits/20260913_101500_edit.json")
        self.assertEqual(status, 200)
        self.assertEqual(parsed["clips"][0]["file"], "day-one/GX010017.MP4")

        status, _, _, parsed = self.request("GET", "/api/edits/defaults")
        self.assertEqual(status, 200)
        self.assertTrue(parsed["filename"].endswith("_edit.json"))

        status, _, _, parsed = self.request(
            "POST",
            "/api/edits",
            {"filename": "morning-ride_edit.json", "output": "morning-ride_video.mp4"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(parsed["document"]["clips"], [])
        self.assertTrue((self.root / "edits" / "morning-ride_edit.json").exists())

        status, _, _, parsed = self.request(
            "POST",
            "/api/edits",
            {"filename": "morning-ride_edit.json", "output": "morning-ride_video.mp4"},
        )
        self.assertEqual(status, 409)
        self.assertIn("already exists", parsed["error"])

    def test_save_save_as_rename_and_delete_edit(self):
        updated_document = {
            "version": 1,
            "output": "20260913_101500_video.mp4",
            "clips": [
                {
                    "file": "day-one/GX010017.MP4",
                    "start": 2.5,
                    "end": 5.5,
                    "label": "Adjusted",
                },
                {
                    "file": "day-one/GX010020.MP4",
                    "start": 0.0,
                    "end": 3.0,
                    "label": "Second",
                },
            ],
        }

        status, _, _, parsed = self.request(
            "PUT",
            "/api/edits/20260913_101500_edit.json",
            {"document": updated_document},
        )
        self.assertEqual(status, 200)
        saved_text = (self.root / "edits" / "20260913_101500_edit.json").read_text(encoding="utf-8")
        self.assertTrue(saved_text.endswith("\n"))
        self.assertEqual(json.loads(saved_text), parsed["document"])

        save_as_document = dict(parsed["document"])
        save_as_document["output"] = "best-parts_video.mp4"
        status, _, _, parsed = self.request(
            "POST",
            "/api/edits/20260913_101500_edit.json/save-as",
            {
                "filename": "best-parts_edit.json",
                "document": save_as_document,
            },
        )
        self.assertEqual(status, 201)
        self.assertTrue((self.root / "edits" / "best-parts_edit.json").exists())
        original = json.loads((self.root / "edits" / "20260913_101500_edit.json").read_text(encoding="utf-8"))
        self.assertEqual(original["output"], "20260913_101500_video.mp4")

        status, _, _, parsed = self.request(
            "POST",
            "/api/edits/best-parts_edit.json/rename",
            {"filename": "renamed-best_edit.json"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(parsed["filename"], "renamed-best_edit.json")
        renamed_text = json.loads((self.root / "edits" / "renamed-best_edit.json").read_text(encoding="utf-8"))
        self.assertEqual(renamed_text["output"], "best-parts_video.mp4")

        status, _, _, _ = self.request("DELETE", "/api/edits/renamed-best_edit.json")
        self.assertEqual(status, 204)
        self.assertFalse((self.root / "edits" / "renamed-best_edit.json").exists())

    def test_rejects_invalid_paths_and_validates_draft_ranges(self):
        status, _, _, parsed = self.request("GET", "/api/edits/%2E%2E%2Fsecret.json")
        self.assertEqual(status, 400)
        self.assertIn("directory separators", parsed["error"])

        status, _, _, parsed = self.request(
            "PUT",
            "/api/edits/20260913_101500_edit.json",
            {
                "document": {
                    "version": 1,
                    "output": "bad_video.mp4",
                    "clips": [
                        {
                            "file": "day-one/GX010017.MP4",
                            "start": 0.0,
                            "end": 20.0,
                        }
                    ],
                }
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("exceeds the source duration", parsed["error"])

    def test_lists_clips_and_streams_media_ranges(self):
        status, _, _, parsed = self.request("GET", "/api/clips")
        self.assertEqual(status, 200)
        self.assertEqual(parsed["clips"][0]["file"], "day-one/GX010017.MP4")
        self.assertEqual(parsed["clips"][0]["duration"], 12.5)

        status, response, data, _ = self.request(
            "GET",
            "/media/day-one/GX010017.MP4",
            headers={"Range": "bytes=2-5"},
        )
        self.assertEqual(status, 206)
        self.assertEqual(data, b"cdef")
        self.assertEqual(response.getheader("Content-Range"), "bytes 2-5/26")
        self.assertEqual(response.getheader("Accept-Ranges"), "bytes")

        status, _, _, parsed = self.request("GET", "/media/..%2Fsecret.mp4")
        self.assertEqual(status, 400)
        self.assertIn("clips directory", parsed["error"])

    def test_lists_and_streams_renders(self):
        status, _, _, parsed = self.request("GET", "/api/renders")
        self.assertEqual(status, 200)
        self.assertEqual(
            [item["filename"] for item in parsed["renders"]],
            ["20260913_111500_video.mp4", "20260913_101500_video.mp4"],
        )

        status, response, data, _ = self.request(
            "GET",
            "/renders/20260913_111500_video.mp4",
            headers={"Range": "bytes=0-5"},
        )
        self.assertEqual(status, 206)
        self.assertEqual(data, b"render")
        self.assertEqual(response.getheader("Content-Range"), "bytes 0-5/15")
        self.assertEqual(response.getheader("Accept-Ranges"), "bytes")

        status, _, _, parsed = self.request("GET", "/renders/..%2Fsecret.mp4")
        self.assertEqual(status, 400)
        self.assertIn("exports directory", parsed["error"])

        status, _, _, parsed = self.request("GET", "/renders/ignore.txt")
        self.assertEqual(status, 400)
        self.assertIn(".mp4 extension", parsed["error"])

        status, _, _, parsed = self.request("GET", "/renders/missing_video.mp4")
        self.assertEqual(status, 404)
        self.assertIn("not found", parsed["error"].lower())

    def test_send_json_ignores_client_disconnect(self):
        handler = object.__new__(EditorRequestHandler)
        handler.send_response = lambda status: None
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None

        class BrokenWriter:
            def write(self, data):
                del data
                raise BrokenPipeError(32, "Broken pipe")

        handler.wfile = BrokenWriter()

        handler._send_json(HTTPStatus.OK, {"ok": True})


if __name__ == "__main__":
    unittest.main()