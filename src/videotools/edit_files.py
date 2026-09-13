from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from videotools.project import VideoProject


def ensure_edits_dir(project: VideoProject) -> Path:
    edits_dir = project.edits_dir
    edits_dir.mkdir(parents=True, exist_ok=True)
    return edits_dir


def create_new_edit_file(project: VideoProject) -> tuple[Path, str]:
    filename = suggested_edit_filename(project)
    return resolve_edit_file(project, filename), output_name_for_edit_filename(filename)


def suggested_edit_filename(project: VideoProject) -> str:
    edits_dir = ensure_edits_dir(project)
    edit_id = _next_edit_id(edits_dir)
    return f"{edit_id}_edit.json"


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


def output_name_for_edit_filename(filename: str) -> str:
    validated = validate_edit_filename(filename)
    stem = Path(validated).stem
    base = stem[:-5] if stem.endswith("_edit") else stem
    return f"{base}_video.mp4"


def validate_edit_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ValueError("Edit filename must be a non-empty string.")

    value = filename.strip()
    if "/" in value or "\\" in value:
        raise ValueError("Edit filename must not include directory separators.")

    path = Path(value)

    if path.is_absolute():
        raise ValueError("Edit filename must not be an absolute path.")

    if len(path.parts) != 1 or path.name != value:
        raise ValueError("Edit filename must not include directory separators.")

    if ".." in path.parts:
        raise ValueError("Edit filename must not contain parent-directory segments.")

    if path.suffix.lower() != ".json":
        raise ValueError("Edit filename must use the .json extension.")

    return value


def resolve_edit_file(project: VideoProject, filename: str) -> Path:
    validated = validate_edit_filename(filename)
    edit_file = (ensure_edits_dir(project) / validated).resolve()

    if not edit_file.is_relative_to(project.edits_dir):
        raise ValueError("Edit filename must stay inside the project's edits directory.")

    return edit_file


def load_edit_document(project: VideoProject, filename: str) -> dict[str, Any]:
    return read_edit_document(resolve_edit_file(project, filename))


def read_edit_document(edit_file: Path) -> dict[str, Any]:
    try:
        raw = json.loads(edit_file.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FileNotFoundError(f"Edit file does not exist: {edit_file}") from error
    except OSError as error:
        raise OSError(f"Could not read edit file {edit_file}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid JSON in {edit_file}: line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error

    if not isinstance(raw, dict):
        raise ValueError("Edit files must contain a JSON object.")

    return raw


def create_empty_edit_document(filename: str, output: str | None = None) -> dict[str, Any]:
    validated = validate_edit_filename(filename)
    return {
        "version": 1,
        "output": output or output_name_for_edit_filename(validated),
        "clips": [],
    }


def create_edit_document(
    project: VideoProject,
    filename: str,
    document: dict[str, Any],
) -> Path:
    edit_file = resolve_edit_file(project, filename)

    if edit_file.exists():
        raise FileExistsError(f"Edit file already exists: {edit_file}")

    _write_json_file(edit_file, document)
    return edit_file


def save_edit_document(
    project: VideoProject,
    filename: str,
    document: dict[str, Any],
) -> Path:
    edit_file = resolve_edit_file(project, filename)

    if not edit_file.exists():
        raise FileNotFoundError(f"Edit file does not exist: {edit_file}")

    _write_json_file_atomically(edit_file, document)
    return edit_file


def rename_edit_file(
    project: VideoProject,
    filename: str,
    new_filename: str,
) -> Path:
    source = resolve_edit_file(project, filename)
    destination = resolve_edit_file(project, new_filename)

    if not source.exists():
        raise FileNotFoundError(f"Edit file does not exist: {source}")
    if destination.exists():
        raise FileExistsError(f"Edit file already exists: {destination}")

    source.replace(destination)
    return destination


def delete_edit_file(project: VideoProject, filename: str) -> None:
    edit_file = resolve_edit_file(project, filename)

    if not edit_file.exists():
        raise FileNotFoundError(f"Edit file does not exist: {edit_file}")

    edit_file.unlink()


def _write_json_file(edit_file: Path, document: dict[str, Any]) -> None:
    edit_file.parent.mkdir(parents=True, exist_ok=True)
    edit_file.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_json_file_atomically(edit_file: Path, document: dict[str, Any]) -> None:
    edit_file.parent.mkdir(parents=True, exist_ok=True)

    file_descriptor, temp_name = tempfile.mkstemp(
        dir=edit_file.parent,
        prefix=".tmp-",
        suffix=".json",
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(document, indent=2, ensure_ascii=False) + "\n"
            )

        temp_path.replace(edit_file)
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _next_edit_id(edits_dir: Path, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    candidate = timestamp
    counter = 2

    while (edits_dir / f"{candidate}_edit.json").exists():
        candidate = f"{timestamp}_{counter}"
        counter += 1

    return candidate