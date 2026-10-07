from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi.testclient import TestClient

from videotools.project import VideoProject
from videotools.services.jobs import MediaJob
from videotools.services.media import resolve_export_video, resolve_project_media
from videotools.services.organize import organize_project_clips
from videotools.web.app import app


class ProjectWorkflowApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        for directory in ("clips/day-one", "edits", "exports", "exports-social"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "project.toml").write_text(
            """\
name = "workflow-project"

[paths]
clips = "clips"
edits = "edits"
exports = "exports"
exports_social = "exports-social"
""",
            encoding="utf-8",
        )
        self.project = VideoProject.load(self.root)
        self.clip = self.project.clips_dir / "day-one" / "same.mp4"
        self.clip.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
        self.render = self.project.exports_dir / "normal.mp4"
        self.render.write_bytes(b"normal-render")
        self.social = self.project.exports_social_dir / "vertical.mp4"
        self.social.write_bytes(b"social-render")
        self.client = TestClient(app)
        self.project_patch = patch(
            "videotools.web.routers.workflows.get_project",
            return_value=SimpleNamespace(path=self.root),
        )
        self.project_patch.start()

    def tearDown(self):
        self.project_patch.stop()
        self.temporary_directory.cleanup()

    def test_edit_api_saves_and_loads_duplicate_occurrences(self):
        created = self.client.post(
            "/api/projects/workflow-project/edits",
            json={"filename": "duplicate_edit.json", "output": "duplicate.mp4"},
        )
        self.assertEqual(created.status_code, 201)

        document = {
            "version": 1,
            "output": "duplicate.mp4",
            "clips": [
                {"file": "day-one/same.mp4", "start": 5, "end": 10, "label": "A"},
                {"file": "day-one/same.mp4", "start": 30, "end": 40, "label": "B"},
            ],
        }
        saved = self.client.put(
            "/api/projects/workflow-project/edits/duplicate_edit.json",
            json={"document": document},
        )
        self.assertEqual(saved.status_code, 200, saved.text)

        loaded = self.client.get(
            "/api/projects/workflow-project/edits/duplicate_edit.json"
        )
        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.json()["clips"], document["clips"])

    def test_media_and_exports_stream_ranges_and_reject_traversal(self):
        response = self.client.get(
            "/api/projects/workflow-project/media/day-one/same.mp4",
            headers={"Range": "bytes=2-5"},
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, b"cdef")
        self.assertEqual(response.headers["content-range"], "bytes 2-5/26")
        self.assertEqual(response.headers["accept-ranges"], "bytes")

        export_response = self.client.get(
            "/api/projects/workflow-project/exports/normal.mp4",
            headers={"Range": "bytes=0-5"},
        )
        self.assertEqual(export_response.status_code, 206)
        self.assertEqual(export_response.content, b"normal")

        social_response = self.client.get(
            "/api/projects/workflow-project/social-exports/vertical.mp4",
            headers={"Range": "bytes=0-5"},
        )
        self.assertEqual(social_response.status_code, 206)
        self.assertEqual(social_response.content, b"social")

        for url, status in (
            ("/api/projects/workflow-project/media/%2E%2E%2Foutside.mp4", 400),
            ("/api/projects/workflow-project/exports/%2E%2E%2Foutside.mp4", 404),
            ("/api/projects/workflow-project/social-exports/%2E%2E%2Foutside.mp4", 404),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status)

        with self.assertRaises(ValueError):
            resolve_project_media(self.project, "../outside.mp4")
        with self.assertRaises(ValueError):
            resolve_export_video(self.project, "../outside.mp4")
        with self.assertRaises(ValueError):
            resolve_export_video(self.project, "../outside.mp4", social=True)

    def test_exports_list_and_social_options_use_existing_supported_choices(self):
        exports = self.client.get("/api/projects/workflow-project/exports")
        self.assertEqual(exports.status_code, 200)
        self.assertEqual([item["filename"] for item in exports.json()["renders"]], ["normal.mp4"])
        self.assertEqual(
            [item["filename"] for item in exports.json()["social_exports"]],
            ["vertical.mp4"],
        )
        self.assertGreater(exports.json()["renders"][0]["size_bytes"], 0)

        options = self.client.get("/api/projects/workflow-project/social-options")
        self.assertEqual(options.status_code, 200)
        self.assertEqual([item["key"] for item in options.json()["presets"]], ["instagram"])
        self.assertEqual([item["key"] for item in options.json()["framing_modes"]], ["crop", "fit"])

    def test_render_api_returns_a_busy_job_then_reports_completion(self):
        self.client.post(
            "/api/projects/workflow-project/edits",
            json={"filename": "render_edit.json", "output": "render.mp4"},
        )
        self.client.put(
            "/api/projects/workflow-project/edits/render_edit.json",
            json={
                "document": {
                    "version": 1,
                    "output": "render.mp4",
                    "clips": [{"file": "day-one/same.mp4", "start": 5, "end": 10}],
                }
            },
        )
        started = Event()
        release = Event()

        def fake_render(timeline, *, overwrite, gpu=False):
            del overwrite, gpu
            started.set()
            release.wait(timeout=3)
            return timeline.output

        with patch("videotools.services.workflows.render_accurate", side_effect=fake_render):
            response = self.client.post(
                "/api/projects/workflow-project/renders",
                json={"edit_filename": "render_edit.json", "mode": "accurate"},
            )
            self.assertEqual(response.status_code, 202, response.text)
            job_id = response.json()["job_id"]
            try:
                self.assertTrue(started.wait(timeout=2))
                running = self.client.get(f"/api/projects/workflow-project/jobs/{job_id}")
                self.assertEqual(running.status_code, 200)
                self.assertEqual(running.json()["status"], "running")

                duplicate = self.client.post(
                    "/api/projects/workflow-project/renders",
                    json={"edit_filename": "render_edit.json", "mode": "accurate"},
                )
                self.assertEqual(duplicate.status_code, 409)
            finally:
                release.set()

        completed = None
        for _ in range(100):
            response = self.client.get(f"/api/projects/workflow-project/jobs/{job_id}")
            completed = response.json()
            if completed["status"] == "completed":
                break
            Event().wait(0.01)

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output_filename"].endswith("_accurate.mp4"), True)

    def test_render_api_defaults_gpu_to_false_and_propagates_true(self):
        self.client.post(
            "/api/projects/workflow-project/edits",
            json={"filename": "gpu_edit.json", "output": "gpu.mp4"},
        )
        self.client.put(
            "/api/projects/workflow-project/edits/gpu_edit.json",
            json={
                "document": {
                    "version": 1,
                    "output": "gpu.mp4",
                    "clips": [{"file": "day-one/same.mp4", "start": 5, "end": 10}],
                }
            },
        )
        seen_gpu: list[bool] = []

        def fake_render(timeline, *, overwrite, gpu=False):
            del overwrite
            seen_gpu.append(gpu)
            return timeline.output

        with patch("videotools.services.workflows.render_accurate", side_effect=fake_render):
            default = self.client.post(
                "/api/projects/workflow-project/renders",
                json={"edit_filename": "gpu_edit.json", "mode": "accurate"},
            )
            self.assertEqual(default.status_code, 202, default.text)
            self._wait_for_completion(default.json()["job_id"])

            enabled = self.client.post(
                "/api/projects/workflow-project/renders",
                json={"edit_filename": "gpu_edit.json", "mode": "accurate", "gpu": True},
            )
            self.assertEqual(enabled.status_code, 202, enabled.text)
            self._wait_for_completion(enabled.json()["job_id"])

        self.assertEqual(seen_gpu, [False, True])

    def test_render_gpu_status_endpoint_reports_availability(self):
        with patch(
            "videotools.web.routers.workflows.gpu_render_status",
            return_value={
                "available": True,
                "encoder": {"key": "nvidia", "name": "NVIDIA NVENC", "codec": "hevc_nvenc"},
                "reason": None,
            },
        ):
            response = self.client.get("/api/projects/workflow-project/render-gpu")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["available"])
        self.assertEqual(body["encoder"]["codec"], "hevc_nvenc")

    def _wait_for_completion(self, job_id: str) -> dict:
        for _ in range(100):
            response = self.client.get(f"/api/projects/workflow-project/jobs/{job_id}")
            body = response.json()
            if body["status"] in {"completed", "failed"}:
                return body
            Event().wait(0.01)
        self.fail(f"Job {job_id} did not finish in time")

    def test_social_export_api_completes_and_lists_the_output(self):
        converted = []

        def fake_convert(*, source, output, preset, framing):
            converted.append((source, preset.key, framing))
            output.write_bytes(b"converted")
            return output

        with patch("videotools.services.workflows.convert_social_video", side_effect=fake_convert):
            response = self.client.post(
                "/api/projects/workflow-project/social-exports",
                json={
                    "source_filename": "normal.mp4",
                    "preset": "instagram",
                    "framing": "fit",
                },
            )
            self.assertEqual(response.status_code, 202, response.text)
            job_id = response.json()["job_id"]

            completed = None
            for _ in range(100):
                job_response = self.client.get(
                    f"/api/projects/workflow-project/jobs/{job_id}"
                )
                completed = job_response.json()
                if completed["status"] == "completed":
                    break
                Event().wait(0.01)

        self.assertEqual(completed["status"], "completed")
        self.assertEqual(converted[0][1:], ("instagram", "fit"))
        exports = self.client.get("/api/projects/workflow-project/exports").json()
        self.assertEqual(
            [item["filename"] for item in exports["social_exports"]],
            ["vertical.mp4", "normal_instagram.mp4"],
        )

    def test_journal_crud_endpoints(self):
        created = self.client.post(
            "/api/projects/workflow-project/journal",
            json={
                "date": "2026-10-02",
                "activity": "Harbor shoot",
                "location": "Cascais",
                "start_time": "08:30",
                "end_time": "10:00",
                "tags": ["gopro", "b-roll"],
                "highlight": "Slow pan over boats",
                "notes": "Use ND filter.",
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        created_entry = created.json()
        entry_id = created_entry["id"]

        listed = self.client.get("/api/projects/workflow-project/journal")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
        self.assertEqual(listed.json()[0]["activity"], "Harbor shoot")

        updated = self.client.put(
            f"/api/projects/workflow-project/journal/{entry_id}",
            json={
                "date": "2026-10-02",
                "activity": "Harbor shoot updated",
                "location": "Cascais",
                "start_time": "08:45",
                "end_time": "10:15",
                "tags": ["gopro", "sunrise"],
                "highlight": "Golden light on docks",
                "notes": "Use wide lens.",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["activity"], "Harbor shoot updated")

        deleted = self.client.delete(
            f"/api/projects/workflow-project/journal/{entry_id}"
        )
        self.assertEqual(deleted.status_code, 204)

        empty = self.client.get("/api/projects/workflow-project/journal")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json(), [])

    def test_probe_and_thumbnails_endpoints_start_jobs(self):
        probe_job = MediaJob(
            job_id="probe123",
            project_id="workflow-project",
            kind="probe",
        )
        thumbnails_job = MediaJob(
            job_id="thumb123",
            project_id="workflow-project",
            kind="thumbnails",
        )

        with patch(
            "videotools.web.routers.workflows.start_probe_job",
            return_value=probe_job,
        ):
            response = self.client.post(
                "/api/projects/workflow-project/probe",
                json={"force": False},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["kind"], "probe")

        with patch(
            "videotools.web.routers.workflows.start_thumbnails_job",
            return_value=thumbnails_job,
        ):
            response = self.client.post(
                "/api/projects/workflow-project/thumbnails",
                json={"force": False},
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["kind"], "thumbnails")

    def test_organize_endpoint_starts_job(self):
        organize_job = MediaJob(
            job_id="organize123",
            project_id="workflow-project",
            kind="organize",
        )

        with patch(
            "videotools.web.routers.workflows.start_organize_job",
            return_value=organize_job,
        ) as start:
            response = self.client.post(
                "/api/projects/workflow-project/organize"
            )
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["kind"], "organize")
            start.assert_called_once()

    def test_organize_service_moves_loose_clips_into_date_folders(self):
        loose = self.project.clips_dir / "loose.mp4"
        loose.write_bytes(b"loose-clip")
        date_dir = self.project.clips_dir / "20260315"
        date_dir.mkdir()
        (date_dir / "duplicate.mp4").write_bytes(b"already-here")
        loose_duplicate = self.project.clips_dir / "duplicate.mp4"
        loose_duplicate.write_bytes(b"conflicting")

        def fake_probe(path):
            return {
                "format": {
                    "tags": {"creation_time": "2026-03-15T12:00:00Z"}
                }
            }

        with patch(
            "videotools.services.organize.probe_video",
            side_effect=fake_probe,
        ):
            result = organize_project_clips(self.project)

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["moved"], 1)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["errors"], [])
        self.assertFalse(loose.exists())
        self.assertTrue((date_dir / "loose.mp4").is_file())
        self.assertTrue(loose_duplicate.exists())
        # Clips already inside folders are left completely alone.
        self.assertTrue(
            (self.project.clips_dir / "day-one" / "same.mp4").is_file()
        )

    def test_organize_service_reports_failures(self):
        broken = self.project.clips_dir / "broken.mp4"
        broken.write_bytes(b"broken")

        with patch(
            "videotools.services.organize.probe_video",
            side_effect=RuntimeError("ffprobe missing"),
        ):
            result = organize_project_clips(self.project)

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["moved"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["errors"], ["broken.mp4: ffprobe missing"])
        self.assertTrue(broken.exists())


if __name__ == "__main__":
    unittest.main()
