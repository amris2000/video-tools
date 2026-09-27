from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

from videotools.config import load_config


@dataclass(frozen=True)
class ProjectPaths:
    clips: str
    metadata: str
    edits: str
    exports: str
    exports_social: str
    journal: str


@dataclass(frozen=True)
class ProjectInfo:
    id: str
    name: str
    path: Path
    timezone: str | None
    paths: ProjectPaths


@dataclass(frozen=True)
class ProjectStats:
    clips: int
    edits: int
    renders: int
    social_exports: int


def get_projects_directory() -> Path:
    config = load_config()

    if config.projects_directory is None:
        raise RuntimeError(
            "Video Tools has not been configured."
        )

    projects_directory = Path(
        config.projects_directory
    )

    if not projects_directory.is_dir():
        raise RuntimeError(
            "Configured projects directory does not exist."
        )

    return projects_directory


def load_project_info(
    directory: Path,
) -> ProjectInfo | None:
    project_file = directory / "project.toml"

    if not project_file.is_file():
        return None

    try:
        with project_file.open("rb") as file:
            project_config = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    configured_paths = project_config.get(
        "paths",
        {},
    )

    paths = ProjectPaths(
        clips=configured_paths.get(
            "clips",
            "clips",
        ),
        metadata=configured_paths.get(
            "metadata",
            "metadata",
        ),
        edits=configured_paths.get(
            "edits",
            "edits",
        ),
        exports=configured_paths.get(
            "exports",
            "exports",
        ),
        exports_social=configured_paths.get(
            "exports_social",
            "exports-social",
        ),
        journal=configured_paths.get(
            "journal",
            "journal.json",
        ),
    )

    return ProjectInfo(
        id=directory.name,
        name=project_config.get(
            "name",
            directory.name,
        ),
        path=directory.resolve(),
        timezone=project_config.get("timezone"),
        paths=paths,
    )


def discover_projects() -> list[ProjectInfo]:
    projects_directory = get_projects_directory()

    projects: list[ProjectInfo] = []

    for directory in projects_directory.iterdir():
        if not directory.is_dir():
            continue

        project = load_project_info(directory)

        if project is not None:
            projects.append(project)

    projects.sort(
        key=lambda project: project.name.lower()
    )

    return projects


def get_project(
    project_id: str,
) -> ProjectInfo | None:
    projects_directory = get_projects_directory()

    project_directory = (
        projects_directory / project_id
    )

    if not project_directory.is_dir():
        return None

    return load_project_info(project_directory)


def count_files(
    directory: Path,
    *,
    suffix: str,
    recursive: bool,
) -> int:
    if not directory.is_dir():
        return 0

    paths = (
        directory.rglob("*")
        if recursive
        else directory.iterdir()
    )

    suffix = suffix.lower()

    return sum(
        1
        for path in paths
        if path.is_file()
        and path.suffix.lower() == suffix
    )


def calculate_project_stats(
    project: ProjectInfo,
) -> ProjectStats:
    return ProjectStats(
        clips=count_files(
            project.path / project.paths.clips,
            suffix=".mp4",
            recursive=True,
        ),
        edits=count_files(
            project.path / project.paths.edits,
            suffix=".json",
            recursive=False,
        ),
        renders=count_files(
            project.path / project.paths.exports,
            suffix=".mp4",
            recursive=False,
        ),
        social_exports=count_files(
            project.path
            / project.paths.exports_social,
            suffix=".mp4",
            recursive=False,
        ),
    )