from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Any, cast

from videotools.edit import load_edit_timeline
from videotools.edit_files import create_render_output_path, list_render_files, list_social_render_files
from videotools.project import VideoProject
from videotools.render import render_accurate, render_fast
from videotools.services.edits import edit_path
from videotools.services.jobs import MediaJob, start_job
from videotools.services.media import resolve_export_video
from videotools.social import (
    FramingMode,
    SOCIAL_PRESETS,
    convert_social_video,
    create_social_output_path,
)


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
) -> MediaJob:
    timeline = load_edit_timeline(edit_path(project, edit_filename), project)
    output = create_render_output_path(project, mode)
    render_timeline = replace(timeline, output=output)
    renderer = render_fast if mode == "fast" else render_accurate
    return start_job(project_id, "render", lambda: renderer(render_timeline, overwrite=False))


def start_social_export(
    project: VideoProject,
    project_id: str,
    source_filename: str,
    preset_key: str,
    framing: str,
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
        ),
    )


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
