from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from videotools.services.projects import (
    ProjectInfo,
    ProjectPaths,
    create_project_in_projects_directory,
    delete_project_from_projects_directory,
)
from videotools.web.app import app


class CreateProjectServiceTests(unittest.TestCase):
    def test_creates_project_in_configured_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            with patch(
                "videotools.services.projects.get_projects_directory",
                return_value=root,
            ):
                info = create_project_in_projects_directory("linux-test")

            self.assertEqual(info.id, "linux-test")
            self.assertEqual(info.name, "linux-test")
            self.assertTrue((root / "linux-test" / "project.toml").is_file())
            self.assertTrue((root / "linux-test" / "journal.json").is_file())

    def test_rejects_invalid_project_names(self):
        for invalid in ("", "   ", ".", "..", "name/with/slash", "name\\with\\slash", "name:bad"):
            with self.subTest(name=invalid):
                with self.assertRaises(ValueError):
                    create_project_in_projects_directory(invalid)


class DeleteProjectServiceTests(unittest.TestCase):
    def test_deletes_project_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "to-delete"
            project.mkdir()
            (project / "project.toml").write_text("name = \"to-delete\"\n", encoding="utf-8")

            with patch(
                "videotools.services.projects.get_projects_directory",
                return_value=root,
            ):
                delete_project_from_projects_directory("to-delete")

            self.assertFalse(project.exists())

    def test_rejects_invalid_project_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch(
                "videotools.services.projects.get_projects_directory",
                return_value=root,
            ):
                with self.assertRaises(ValueError):
                    delete_project_from_projects_directory("../outside")

    def test_requires_project_marker(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "no-marker"
            project.mkdir()

            with patch(
                "videotools.services.projects.get_projects_directory",
                return_value=root,
            ):
                with self.assertRaises(ValueError):
                    delete_project_from_projects_directory("no-marker")


class ProjectsApiCreateTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_create_project_returns_201(self):
        project = ProjectInfo(
            id="new-project",
            name="new-project",
            path=Path("/tmp/new-project"),
            timezone="Europe/Copenhagen",
            paths=ProjectPaths(
                clips="clips",
                metadata="metadata",
                edits="edits",
                exports="exports",
                exports_social="exports-social",
                journal="journal.json",
            ),
        )

        with patch(
            "videotools.web.routers.projects.create_project_in_projects_directory",
            return_value=project,
        ):
            response = self.client.post(
                "/api/projects",
                json={"name": "new-project"},
            )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["id"], "new-project")
        self.assertEqual(data["name"], "new-project")

    def test_create_project_maps_conflicts(self):
        with patch(
            "videotools.web.routers.projects.create_project_in_projects_directory",
            side_effect=FileExistsError("Project already exists."),
        ):
            response = self.client.post(
                "/api/projects",
                json={"name": "new-project"},
            )

        self.assertEqual(response.status_code, 409)


class ProjectsApiDeleteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_delete_project_returns_204(self):
        with patch(
            "videotools.web.routers.projects.delete_project_from_projects_directory",
            return_value=None,
        ):
            response = self.client.delete("/api/projects/new-project")

        self.assertEqual(response.status_code, 204)

    def test_delete_project_maps_missing(self):
        with patch(
            "videotools.web.routers.projects.delete_project_from_projects_directory",
            side_effect=FileNotFoundError("Project not found."),
        ):
            response = self.client.delete("/api/projects/new-project")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
