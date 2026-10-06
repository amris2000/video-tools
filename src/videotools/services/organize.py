"""Organize loose clips into date-based folders inside the clips directory.

Reusable service-layer functionality shared by the CLI, the FastAPI
maintenance endpoint, and the import pipeline. Only loose video files
directly inside the clips directory are considered; existing folders are
left completely alone.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Callable, Iterable

from videotools.metadata import (
    VIDEO_EXTENSIONS,
    get_creation_time,
    parse_creation_time,
    probe_video,
)
from videotools.project import VideoProject

DATE_FOLDER_FORMAT = "%Y%m%d"
DEFAULT_TIMEZONE = "Europe/Copenhagen"

ProgressCallback = Callable[[dict[str, Any]], None]


def list_loose_clips(project: VideoProject) -> list[Path]:
    """Return loose video clips directly inside the project's clips directory."""
    clips_dir = project.clips_dir

    if not clips_dir.exists():
        raise RuntimeError(
            f"Clips directory does not exist: {clips_dir}"
        )

    return sorted(
        path
        for path in clips_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def _publish(
    progress_callback: ProgressCallback | None,
    event: dict[str, Any],
) -> None:
    if progress_callback is not None:
        progress_callback(event)


def organize_project_clips(
    project: VideoProject,
    clips: Iterable[Path] | None = None,
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Move loose clips into ``YYYYMMDD`` date folders based on creation time.

    When ``clips`` is omitted, all loose clips in the project's clips
    directory are organized. An explicit ``clips`` iterable restricts the
    operation to those files (used by the import pipeline).

    Returns a JSON-serializable summary with per-clip entries.
    """
    clips_dir = project.clips_dir

    if clips is None:
        targets = list_loose_clips(project)
    else:
        clips_root = clips_dir.resolve()
        targets = sorted(
            Path(clip)
            for clip in clips
            if Path(clip).is_file()
            and Path(clip).suffix.lower() in VIDEO_EXTENSIONS
            and Path(clip).parent.resolve() == clips_root
        )

    timezone_name = project.config.get("timezone", DEFAULT_TIMEZONE)
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        timezone_name = DEFAULT_TIMEZONE

    total = len(targets)
    moved = 0
    skipped = 0
    failed = 0
    entries: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, clip in enumerate(targets, start=1):
        _publish(
            progress_callback,
            {
                "status": "running",
                "current_file": clip.name,
                "completed": index - 1,
                "total": total,
            },
        )

        entry: dict[str, Any] = {
            "clip": str(clip),
            "filename": clip.name,
            "outcome": None,
            "destination": None,
            "reason": None,
        }

        try:
            info = probe_video(clip)
            creation_time = get_creation_time(info)

            if not creation_time:
                entry["outcome"] = "skipped"
                entry["reason"] = "no creation timestamp found"
            else:
                local_time = parse_creation_time(
                    creation_time,
                    timezone_name,
                )

                if local_time is None:
                    entry["outcome"] = "skipped"
                    entry["reason"] = "could not parse creation timestamp"
                else:
                    date_folder = local_time.strftime(DATE_FOLDER_FORMAT)
                    destination_dir = clips_dir / date_folder
                    destination = destination_dir / clip.name

                    # Never overwrite an existing file.
                    if destination.exists():
                        entry["outcome"] = "skipped"
                        entry["reason"] = (
                            f"already exists in {date_folder}/"
                        )
                    else:
                        destination_dir.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                        shutil.move(str(clip), str(destination))
                        entry["outcome"] = "moved"
                        entry["destination"] = str(destination)
                        entry["reason"] = f"{date_folder}/{clip.name}"

        except Exception as error:
            entry["outcome"] = "failed"
            entry["reason"] = str(error)
            errors.append(f"{clip.name}: {error}")

        if entry["outcome"] == "moved":
            moved += 1
        elif entry["outcome"] == "failed":
            failed += 1
        else:
            skipped += 1

        entries.append(entry)
        _publish(
            progress_callback,
            {
                "status": "completed",
                "current_file": clip.name,
                "completed": index,
                "total": total,
                "outcome": entry["outcome"],
                "detail": entry["reason"],
            },
        )

    return {
        "total": total,
        "moved": moved,
        "skipped": skipped,
        "failed": failed,
        "entries": entries,
        "errors": errors,
    }
