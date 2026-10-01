from __future__ import annotations

from pathlib import Path, PurePosixPath
import os
import shutil
from typing import Any

from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject
from videotools.services.gopro import discover_gopro_videos


def create_import_plan(project: VideoProject, source_path: str) -> dict[str, Any]:
    source = _source_directory(source_path)
    existing = _project_clip_inventory(project)
    files = []

    for path in discover_gopro_videos(source):
        relative = path.relative_to(source).as_posix()
        size = path.stat().st_size
        known_sizes = existing.get(path.name.casefold(), set())
        if size in known_sizes:
            status = "already_imported"
        elif known_sizes:
            status = "conflict"
        else:
            status = "new"
        files.append({
            "source_relative_path": relative,
            "filename": path.name,
            "size_bytes": size,
            "status": status,
        })

    source_names: dict[str, list[dict[str, Any]]] = {}
    for item in files:
        source_names.setdefault(item["filename"].casefold(), []).append(item)
    for duplicate_items in source_names.values():
        if len(duplicate_items) > 1:
            for item in duplicate_items:
                if item["status"] == "new":
                    item["status"] = "conflict"

    return {
        "source": str(source),
        "total_source_files": len(files),
        "already_imported": sum(item["status"] == "already_imported" for item in files),
        "new_files": sum(item["status"] == "new" for item in files),
        "conflicts": sum(item["status"] == "conflict" for item in files),
        "files": files,
    }


def import_selected_files(
    project: VideoProject,
    source_path: str,
    selected_paths: list[str],
) -> dict[str, Any]:
    source = _source_directory(source_path)
    plan = create_import_plan(project, str(source))
    entries = {item["source_relative_path"]: item for item in plan["files"]}
    selected = list(dict.fromkeys(selected_paths))
    imported = 0
    skipped = 0
    conflicts = 0
    errors: list[str] = []

    for value in selected:
        try:
            relative = _safe_relative_path(value)
        except ValueError as error:
            conflicts += 1
            errors.append(str(error))
            continue

        entry = entries.get(relative)
        if entry is None:
            conflicts += 1
            errors.append(f"Selected file was not found in the current scan: {relative}")
            continue
        if entry["status"] != "new":
            skipped += 1
            if entry["status"] == "conflict":
                conflicts += 1
            continue

        try:
            source_file = _contained_file(source, relative)
            if source_file.stat().st_size != entry["size_bytes"]:
                conflicts += 1
                errors.append(f"Source changed after scan: {relative}")
                continue
            destination = _contained_destination(project, entry["filename"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination = _contained_destination(project, entry["filename"])
            _copy_without_overwrite(source_file, destination)
        except FileExistsError:
            conflicts += 1
            errors.append(f"Destination already exists: {relative}")
            continue
        except (OSError, ValueError) as error:
            conflicts += 1
            errors.append(f"Could not import {relative}: {error}")
            continue

        imported += 1

    return {
        "imported": imported,
        "skipped": skipped,
        "conflicts": conflicts,
        "errors": errors,
    }


def _source_directory(value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A GoPro source directory is required.")
    source = Path(value).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"GoPro source directory does not exist: {source}")
    if not source.is_dir():
        raise NotADirectoryError(f"GoPro source is not a directory: {source}")
    return source


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("A selected source-relative path is required.")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ":" in normalized or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Selected path must stay inside the scanned source directory.")
    if Path(path.name).suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Selected file is not a supported video type.")
    return path.as_posix()


def _contained_file(source: Path, relative: str) -> Path:
    candidate = (source / Path(*PurePosixPath(relative).parts)).resolve()
    if not candidate.is_relative_to(source):
        raise ValueError("Selected file must stay inside the scanned source directory.")
    if not candidate.is_file() or candidate.suffix.lower() not in VIDEO_EXTENSIONS:
        raise FileNotFoundError(f"Supported source video was not found: {relative}")
    return candidate


def _contained_destination(project: VideoProject, relative: str) -> Path:
    root = project.clips_dir.resolve()
    filename = PurePosixPath(relative)
    if filename.is_absolute() or len(filename.parts) != 1 or filename.name != relative:
        raise ValueError("Import destination must be a filename inside the project's clips directory.")
    destination = (root / filename.name).resolve()
    if not destination.is_relative_to(root):
        raise ValueError("Import destination must stay inside the project's clips directory.")
    return destination


def _project_clip_inventory(project: VideoProject) -> dict[str, set[int]]:
    inventory: dict[str, set[int]] = {}
    root = project.clips_dir.resolve()
    if not root.is_dir():
        return inventory
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                continue
            inventory.setdefault(path.name.casefold(), set()).add(path.stat().st_size)
        except OSError:
            continue
    return inventory


def _copy_without_overwrite(source: Path, destination: Path) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as target_file, source.open("rb") as source_file:
            shutil.copyfileobj(source_file, target_file, length=1024 * 1024)
        shutil.copystat(source, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
