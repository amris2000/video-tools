from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Any, cast

from videotools.edit import load_edit_timeline
from videotools.edit_files import create_render_output_path, list_render_files, list_social_render_files
from videotools.gpu_encoders import gpu_acceleration_status
from videotools.metadata import analyze_project
from videotools.project import VideoProject
from videotools.render import render_accurate, render_fast
from videotools.services.edits import edit_path
from videotools.services.jobs import MediaJob, start_job, start_progress_job
from videotools.services.media import resolve_export_video
from videotools.services.organize import organize_project_clips
from videotools.social import (
    FramingMode,
    SOCIAL_PRESETS,
    convert_social_video,
    create_social_output_path,
)
from videotools.thumbnails import generate_thumbnail, thumbnail_name
from videotools.media import VIDEO_EXTENSIONS


def list_exports(project: VideoProject, project_id: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "renders": [_export_entry(path, project_id, social=False) for path in list_render_files(project)],
        "social_exports": [
            _export_entry(path, project_id, social=True)
            for path in list_social_render_files(project)
        ],
    }


def social_options() -> dict[str, Any]:
    return {
        "presets": [
            {"key": preset.key, "name": preset.name, "description": preset.description}
            for preset in SOCIAL_PRESETS
        ],
        "framing_modes": [
            {"key": "crop", "name": "Crop to fill"},
            {"key": "fit", "name": "Fit with padding"},
        ],
    }


def start_render(
    project: VideoProject,
    project_id: str,
    edit_filename: str,
    mode: str,
    gpu: bool = False,
) -> MediaJob:
    timeline = load_edit_timeline(edit_path(project, edit_filename), project)
    output = create_render_output_path(project, mode)
    render_timeline = replace(timeline, output=output)

    def run() -> Path:
        if mode == "fast":
            return render_fast(render_timeline, overwrite=False)
        return render_accurate(render_timeline, overwrite=False, gpu=gpu)

    return start_job(project_id, "render", run)


def gpu_render_status() -> dict[str, object]:
    """Report GPU encoding availability for the render page."""

    return gpu_acceleration_status()


def gpu_social_status() -> dict[str, object]:
    """Report GPU encoding availability for social exports (H.264)."""

    return gpu_acceleration_status(codec="h264")


def start_social_export(
    project: VideoProject,
    project_id: str,
    source_filename: str,
    preset_key: str,
    framing: str,
    gpu: bool = False,
) -> MediaJob:
    source = resolve_export_video(project, source_filename)
    preset = next((item for item in SOCIAL_PRESETS if item.key == preset_key), None)
    if preset is None:
        raise ValueError("Unsupported social export preset.")
    if framing not in {"crop", "fit"}:
        raise ValueError("Framing mode must be 'crop' or 'fit'.")

    output = create_social_output_path(project, source, preset)
    selected_framing = framing  # validated against the supported Literal values
    return start_job(
        project_id,
        "social_export",
        lambda: convert_social_video(
            source=source,
            output=output,
            preset=preset,
            framing=cast(FramingMode, selected_framing),
            gpu=gpu,
        ),
    )


def start_organize_job(
    project: VideoProject,
    project_id: str,
) -> MediaJob:
    return start_progress_job(
        project_id,
        "organize",
        lambda update: organize_project_clips(
            project,
            progress_callback=update,
        ),
    )


def start_probe_job(
    project: VideoProject,
    project_id: str,
    *,
    force: bool = False,
) -> MediaJob:
    return start_progress_job(
        project_id,
        "probe",
        lambda update: _probe_project(
            project,
            force=force,
            update_progress=update,
        ),
    )


def start_thumbnails_job(
    project: VideoProject,
    project_id: str,
    *,
    force: bool = False,
) -> MediaJob:
    return start_progress_job(
        project_id,
        "thumbnails",
        lambda update: _generate_project_thumbnails(
            project,
            force=force,
            update_progress=update,
        ),
    )


def _probe_project(
    project: VideoProject,
    *,
    force: bool,
    update_progress,
) -> dict[str, Any]:
    errors: list[str] = []

    def progress(event: dict[str, Any]) -> None:
        update_progress(event)
        if event.get("status") == "failed" and event.get("error"):
            errors.append(str(event["error"]))

    report = analyze_project(
        project.root,
        force=force,
        project=project,
        progress_callback=progress,
    )

    summary = report.get("summary", {}) if isinstance(report, dict) else {}

    return {
        "clip_count": summary.get("clip_count", 0),
        "errors": errors,
    }


def _generate_project_thumbnails(
    project: VideoProject,
    *,
    force: bool,
    update_progress,
) -> dict[str, Any]:
    clips = sorted(
        path
        for path in project.clips_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not clips:
        raise RuntimeError(
            f"No video clips found in {project.clips_dir}"
        )

    thumbnails_dir = project.metadata_dir / "thumbnails"
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    errors: list[str] = []

    for index, clip in enumerate(clips, start=1):
        output_file = thumbnails_dir / thumbnail_name(clip, project.root)

        update_progress(
            {
                "status": "running",
                "current_file": clip.name,
                "completed": index - 1,
                "total": len(clips),
            }
        )

        if output_file.exists() and not force:
            skipped += 1
            update_progress(
                {
                    "status": "completed",
                    "current_file": None,
                    "completed": index,
                    "total": len(clips),
                }
            )
            continue

        try:
            generate_thumbnail(clip, output_file)
            generated += 1
            update_progress(
                {
                    "status": "completed",
                    "current_file": None,
                    "completed": index,
                    "total": len(clips),
                }
            )
        except Exception as error:
            errors.append(f"{clip.name}: {error}")
            update_progress(
                {
                    "status": "failed",
                    "current_file": clip.name,
                    "completed": index,
                    "total": len(clips),
                    "error": str(error),
                }
            )

    return {
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
    }


def _export_entry(path: Path, project_id: str, *, social: bool) -> dict[str, Any]:
    stat = path.stat()
    category = "social" if social else "render"
    endpoint = "social-exports" if social else "exports"
    return {
        "filename": path.name,
        "category": category,
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "url": f"/api/projects/{project_id}/{endpoint}/{path.name}",
    }
