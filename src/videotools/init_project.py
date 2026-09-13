from pathlib import Path
import json


def create_project(
    name: str,
    parent: Path | None = None,
) -> Path:
    """Create a new video-tools project."""

    parent = Path(
        parent or Path.cwd()
    ).resolve()

    project_dir = parent / name

    if project_dir.exists():
        raise FileExistsError(
            f"Project already exists: {project_dir}"
        )

    # Create directories
    project_dir.mkdir()

    (project_dir / "clips").mkdir()

    (project_dir / "edits").mkdir()

    (
        project_dir
        / "metadata"
        / "thumbnails"
    ).mkdir(
        parents=True
    )

    (project_dir / "exports").mkdir()

    (project_dir / "exports-social").mkdir()

    # Create project.toml
    project_toml = f"""\
name = "{name}"
timezone = "Europe/Copenhagen"

[paths]
clips = "clips"
edits = "edits"
metadata = "metadata"
exports = "exports"
exports_social = "exports-social"
journal = "journal.json"

[resolve]
project_name = "{name}"
"""

    (
        project_dir
        / "project.toml"
    ).write_text(
        project_toml,
        encoding="utf-8",
    )

    # Create empty journal
    journal = {
        "entries": []
    }

    (
        project_dir
        / "journal.json"
    ).write_text(
        json.dumps(
            journal,
            indent=2,
        ),
        encoding="utf-8",
    )

    return project_dir