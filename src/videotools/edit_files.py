from __future__ import annotations

from datetime import datetime
from pathlib import Path

from videotools.project import VideoProject


def ensure_edits_dir(project: VideoProject) -> Path:
    edits_dir = project.edits_dir
    edits_dir.mkdir(parents=True, exist_ok=True)
    return edits_dir


def create_new_edit_file(project: VideoProject) -> tuple[Path, str]:
    edits_dir = ensure_edits_dir(project)
    edit_id = _next_edit_id(edits_dir)
    return edits_dir / f"{edit_id}_edit.json", f"{edit_id}_video.mp4"


def list_edit_files(project: VideoProject) -> list[Path]:
    edits_dir = ensure_edits_dir(project)
    return sorted(
        (
            path
            for path in edits_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".json"
        ),
        reverse=True,
    )


def _next_edit_id(edits_dir: Path, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    candidate = timestamp
    counter = 2

    while (edits_dir / f"{candidate}_edit.json").exists():
        candidate = f"{timestamp}_{counter}"
        counter += 1

    return candidate