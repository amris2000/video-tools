from __future__ import annotations

from copy import deepcopy
from pathlib import Path, PurePosixPath
import os
import shutil
from typing import Any, Callable

from videotools.metadata import analyze_project, load_existing_report
from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject
from videotools.services.gopro import discover_gopro_videos
from videotools.services.gopro_camera import (
    CameraMedia,
    download_camera_media,
    list_camera_media,
    usb_camera_base_url,
)
from videotools.thumbnails import generate_thumbnail, thumbnail_name


def create_import_plan(project: VideoProject, source_path: str) -> dict[str, Any]:
    camera_url = usb_camera_base_url(source_path)
    camera_files: list[CameraMedia] = []
    if camera_url:
        camera_files = list_camera_media(camera_url)
        source_files = [
            (item.source_relative_path, item.filename, item.size_bytes)
            for item in camera_files
        ]
        source_label = camera_url
    else:
        source = _source_directory(source_path)
        source_files = [
            (path.relative_to(source).as_posix(), path.name, path.stat().st_size)
            for path in discover_gopro_videos(source)
        ]
        source_label = str(source)

    existing = _project_clip_inventory(project)
    files = []

    for relative, filename, size in source_files:
        known_sizes = existing.get(filename.casefold(), set())
        if size in known_sizes:
            status = "already_imported"
        elif known_sizes:
            status = "conflict"
        else:
            status = "new"
        files.append({
            "source_relative_path": relative,
            "filename": filename,
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
        "source": source_label,
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
    *,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    camera_url = usb_camera_base_url(source_path)
    source = None if camera_url else _source_directory(source_path)
    plan = create_import_plan(project, camera_url or str(source))
    entries = {item["source_relative_path"]: item for item in plan["files"]}
    camera_files = {
        item.source_relative_path: item
        for item in list_camera_media(camera_url)
    } if camera_url else {}
    selected = list(dict.fromkeys(selected_paths))
    imported = 0
    skipped = 0
    conflicts = 0
    errors: list[str] = []
    imported_files: list[dict[str, str]] = []
    selected_new_count = sum(
        entries.get(value.replace("\\", "/"), {}).get("status") == "new"
        for value in selected
    )
    completed_new_count = 0

    def report_import(status: str, filename: str, error: str | None = None) -> None:
        nonlocal completed_new_count
        if status in {"completed", "failed"}:
            completed_new_count += 1
        if progress_callback:
            progress_callback({
                "status": status,
                "current_file": filename if status == "running" else None,
                "completed": completed_new_count,
                "total": selected_new_count,
                "error": error,
            })

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

        report_import("running", entry["filename"])
        try:
            destination = _contained_destination(project, entry["filename"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination = _contained_destination(project, entry["filename"])
            if camera_url:
                camera_media = camera_files.get(relative)
                if camera_media is None or camera_media.size_bytes != entry["size_bytes"]:
                    conflicts += 1
                    errors.append(f"Camera media changed after scan: {relative}")
                    report_import("failed", entry["filename"], errors[-1])
                    continue
                _download_camera_without_overwrite(camera_url, camera_media, destination)
            else:
                source_file = _contained_file(source, relative)
                if source_file.stat().st_size != entry["size_bytes"]:
                    conflicts += 1
                    errors.append(f"Source changed after scan: {relative}")
                    report_import("failed", entry["filename"], errors[-1])
                    continue
                _copy_without_overwrite(source_file, destination)
        except FileExistsError:
            conflicts += 1
            errors.append(f"Destination already exists: {relative}")
            report_import("failed", entry["filename"], errors[-1])
            continue
        except (OSError, ValueError) as error:
            conflicts += 1
            errors.append(f"Could not import {relative}: {error}")
            report_import("failed", entry["filename"], errors[-1])
            continue

        imported += 1
        imported_files.append({
            "filename": entry["filename"],
            "source_relative_path": relative,
        })
        report_import("completed", entry["filename"])

    return {
        "imported": imported,
        "skipped": skipped,
        "conflicts": conflicts,
        "errors": errors,
        "imported_files": imported_files,
    }


def run_import_pipeline(
    project: VideoProject,
    source_path: str,
    selected_paths: list[str],
    update_progress: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    plan = create_import_plan(project, source_path)
    entries = {item["source_relative_path"]: item for item in plan["files"]}
    errors: list[str] = []
    stages: dict[str, dict[str, Any]] = {
        name: {
            "status": "waiting",
            "current_file": None,
            "completed": 0,
            "total": 0,
            "errors": [],
        }
        for name in ("import", "thumbnails", "probe")
    }
    progress: dict[str, Any] = {"stage": "import", "stages": stages}

    def publish() -> None:
        update_progress(deepcopy(progress))

    def add_error(stage_name: str, message: str) -> None:
        errors.append(message)
        stages[stage_name]["errors"].append(message)

    selected: list[tuple[str, dict[str, Any]]] = []
    for value in dict.fromkeys(selected_paths):
        try:
            relative = _safe_relative_path(value)
        except ValueError as error:
            add_error("import", str(error))
            continue
        item = entries.get(relative)
        if item is None:
            add_error("import", f"Selected file was not in the current scan: {relative}")
            continue
        selected.append((relative, item))

    conflicts = sum(item["status"] == "conflict" for _, item in selected)
    for relative, item in selected:
        if item["status"] == "conflict":
            add_error("import", f"Conflicting local file was not processed: {relative}")

    new_paths = [relative for relative, item in selected if item["status"] == "new"]
    stages["import"]["total"] = len(new_paths)
    stages["import"]["status"] = "running" if new_paths else "completed"
    publish()

    copy_result = import_selected_files(
        project,
        plan["source"],
        new_paths,
        progress_callback=lambda event: _update_import_progress(
            event, progress, stages, add_error, publish
        ),
    ) if new_paths else {"imported": 0, "skipped": 0, "conflicts": 0, "errors": [], "imported_files": []}

    for message in copy_result["errors"]:
        if message not in errors:
            errors.append(message)
        if message not in stages["import"]["errors"]:
            stages["import"]["errors"].append(message)
    conflicts += copy_result["conflicts"]
    imported_paths = {
        (project.clips_dir / item["filename"]).resolve()
        for item in copy_result["imported_files"]
    }
    stage_import_errors = bool(stages["import"]["errors"] or copy_result["errors"])
    stages["import"].update(
        status="failed" if stage_import_errors else "completed",
        current_file=None,
        completed=max(stages["import"]["completed"], stages["import"]["total"]),
    )
    skipped = copy_result["skipped"]

    local_matches = _project_clip_candidates(project)
    target_clips: dict[Path, Path] = {}
    clips_root = project.clips_dir.resolve()
    for imported_path in imported_paths:
        if imported_path.is_relative_to(clips_root) and imported_path.is_file():
            target_clips[imported_path] = imported_path

    for relative, item in selected:
        if item["status"] != "already_imported":
            continue
        matches = local_matches.get((item["filename"].casefold(), item["size_bytes"]), [])
        if len(matches) != 1:
            skipped += 1
            conflicts += 1
            add_error("import", f"Could not uniquely match existing local clip: {relative}")
            continue
        target_clips[matches[0]] = matches[0]
        skipped += 1

    relevant_clips = sorted(target_clips)
    thumbnail_work = [
        clip for clip in relevant_clips
        if not _thumbnail_path(project, clip).is_file()
    ]
    stages["thumbnails"].update(
        status="running" if thumbnail_work else "completed",
        completed=0,
        total=len(thumbnail_work),
    )
    progress["stage"] = "thumbnails"
    publish()

    for index, clip in enumerate(thumbnail_work, start=1):
        stage = stages["thumbnails"]
        stage.update(status="running", current_file=clip.name, completed=index - 1)
        publish()
        try:
            thumbnail_file = _thumbnail_path(project, clip)
            thumbnail_file.parent.mkdir(parents=True, exist_ok=True)
            generate_thumbnail(clip, thumbnail_file)
        except Exception as error:
            add_error("thumbnails", f"{clip.name}: {error}")
        stage.update(completed=index, current_file=None)

    stages["thumbnails"]["status"] = (
        "failed" if stages["thumbnails"]["errors"] else "completed"
    )
    publish()

    probe_work = _clips_missing_probe_metadata(project, relevant_clips)
    stages["probe"].update(
        status="running" if probe_work else "completed",
        completed=0,
        total=len(probe_work),
    )
    progress["stage"] = "probe"
    publish()

    if probe_work:
        def probe_progress(event: dict[str, Any]) -> None:
            stage = stages["probe"]
            stage.update(
                status="running",
                current_file=event.get("current_file") if event.get("status") == "running" else None,
                completed=event.get("completed", stage["completed"]),
            )
            if event.get("status") == "failed" and event.get("error"):
                add_error("probe", f"{event.get('current_file')}: {event['error']}")
            publish()

        try:
            analyze_project(
                project.root,
                project=project,
                clip_paths=probe_work,
                progress_callback=probe_progress,
            )
        except Exception as error:
            add_error("probe", str(error))
        stages["probe"]["current_file"] = None

    stages["probe"]["status"] = "failed" if stages["probe"]["errors"] else "completed"
    progress["stage"] = None
    publish()
    return {
        "imported": copy_result["imported"],
        "skipped": skipped,
        "conflicts": conflicts,
        "errors": errors,
        "everything_up_to_date": (
            not errors
            and conflicts == 0
            and not any(stage["total"] for stage in stages.values())
        ),
        "stages": deepcopy(stages),
    }


def _update_import_progress(
    event: dict[str, Any],
    progress: dict[str, Any],
    stages: dict[str, dict[str, Any]],
    add_error: Callable[[str, str], None],
    publish: Callable[[], None],
) -> None:
    stage = stages["import"]
    stage.update(
        status="running" if event["status"] == "running" else stage["status"],
        current_file=event.get("current_file"),
        completed=event.get("completed", stage["completed"]),
    )
    if event.get("error"):
        add_error("import", f"{event.get('current_file') or 'Import'}: {event['error']}")
    progress["stage"] = "import"
    publish()


def _project_clip_candidates(project: VideoProject) -> dict[tuple[str, int], list[Path]]:
    candidates: dict[tuple[str, int], list[Path]] = {}
    root = project.clips_dir.resolve()
    if not root.is_dir():
        return candidates
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved.is_relative_to(root):
                candidates.setdefault((path.name.casefold(), path.stat().st_size), []).append(resolved)
        except OSError:
            continue
    return candidates


def _thumbnail_path(project: VideoProject, clip: Path) -> Path:
    return project.metadata_dir / "thumbnails" / thumbnail_name(clip, project.root)


def _clips_missing_probe_metadata(project: VideoProject, clips: list[Path]) -> list[Path]:
    report = load_existing_report(project.metadata_dir / "clip_report.json") or {}
    existing = {
        item.get("relative_path"): item
        for item in report.get("clips", [])
        if isinstance(item, dict) and item.get("relative_path")
    } if isinstance(report, dict) else {}
    missing = []
    for clip in clips:
        stat = clip.stat()
        relative = clip.relative_to(project.root).as_posix()
        metadata = existing.get(relative)
        if not metadata or metadata.get("size_bytes") != stat.st_size or metadata.get("modified_time_ns") != stat.st_mtime_ns:
            missing.append(clip)
    return missing


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


def _project_clip_candidates(
    project: VideoProject,
) -> dict[tuple[str, int], list[Path]]:
    candidates: dict[tuple[str, int], list[Path]] = {}
    root = project.clips_dir.resolve()
    if not root.is_dir():
        return candidates
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if resolved.is_relative_to(root):
                candidates.setdefault(
                    (path.name.casefold(), path.stat().st_size),
                    [],
                ).append(resolved)
        except OSError:
            continue
    return candidates


def _thumbnail_path(project: VideoProject, clip: Path) -> Path:
    return project.metadata_dir / "thumbnails" / thumbnail_name(clip, project.root)


def _clips_missing_probe_metadata(
    project: VideoProject,
    clips: list[Path],
) -> list[Path]:
    report = load_existing_report(project.metadata_dir / "clip_report.json") or {}
    report_clips = report.get("clips", []) if isinstance(report, dict) else []
    existing = {
        item.get("relative_path"): item
        for item in report_clips
        if isinstance(item, dict) and item.get("relative_path")
    } if isinstance(report_clips, list) else {}

    missing = []
    for clip in clips:
        try:
            stat = clip.stat()
        except OSError:
            missing.append(clip)
            continue
        relative = clip.relative_to(project.root).as_posix()
        metadata = existing.get(relative)
        if (
            not metadata
            or metadata.get("size_bytes") != stat.st_size
            or metadata.get("modified_time_ns") != stat.st_mtime_ns
        ):
            missing.append(clip)
    return missing


def _copy_without_overwrite(source: Path, destination: Path) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as target_file, source.open("rb") as source_file:
            shutil.copyfileobj(source_file, target_file, length=1024 * 1024)
        shutil.copystat(source, destination)
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def _download_camera_without_overwrite(
    camera_url: str,
    media: CameraMedia,
    destination: Path,
) -> None:
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
    try:
        with os.fdopen(descriptor, "wb") as target_file:
            download_camera_media(camera_url, media, target_file)
        if destination.stat().st_size != media.size_bytes:
            raise OSError("Downloaded file size did not match the camera media list.")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
