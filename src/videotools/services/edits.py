from __future__ import annotations

from pathlib import Path
from typing import Any

from videotools.edit_files import (
    create_edit_document,
    create_empty_edit_document,
    delete_edit_file,
    list_edit_files,
    load_edit_document,
    output_name_for_edit_filename,
    rename_edit_file,
    save_edit_document,
    suggested_edit_filename,
    validate_edit_filename,
)
from videotools.editor_validation import validate_editor_document
from videotools.project import VideoProject


def list_edits(project: VideoProject) -> list[dict[str, Any]]:
    edits = []
    for edit_file in list_edit_files(project):
        try:
            document = load_edit_document(project, edit_file.name)
            clips = document.get("clips", [])
            clip_count = len(clips) if isinstance(clips, list) else None
        except (OSError, ValueError):
            clip_count = None
        edits.append({"filename": edit_file.name, "clip_count": clip_count})
    return edits


def get_edit(project: VideoProject, filename: str) -> dict[str, Any]:
    document = load_edit_document(project, filename)
    return validate_editor_document(document, project)


def create_edit(
    project: VideoProject,
    filename: str | None = None,
    output: str | None = None,
) -> tuple[str, dict[str, Any]]:
    selected_filename = validate_edit_filename(filename or suggested_edit_filename(project))
    selected_output = output or output_name_for_edit_filename(selected_filename)
    document = create_empty_edit_document(selected_filename, selected_output)
    validated = validate_editor_document(document, project)
    create_edit_document(project, selected_filename, validated)
    return selected_filename, validated


def save_edit(
    project: VideoProject,
    filename: str,
    document: Any,
) -> dict[str, Any]:
    validated = validate_editor_document(document, project)
    save_edit_document(project, filename, validated)
    return validated


def rename_edit(project: VideoProject, filename: str, new_filename: str) -> str:
    return rename_edit_file(project, filename, new_filename).name


def delete_edit(project: VideoProject, filename: str) -> None:
    delete_edit_file(project, filename)


def edit_path(project: VideoProject, filename: str) -> Path:
    from pathlib import Path
    from videotools.edit_files import resolve_edit_file

    return resolve_edit_file(project, filename)
