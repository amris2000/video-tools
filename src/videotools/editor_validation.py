from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from videotools.edit import EditValidationError
from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject

_ROOT_FIELDS = {"version", "output", "clips"}
_CLIP_FIELDS = {"file", "start", "end", "label"}
_FUTURE_CLIP_FIELDS = {
    "speed",
    "volume",
    "fade_in",
    "fade_out",
}


def validate_editor_document(
    raw: Any,
    project: VideoProject,
    *,
    durations: Mapping[str, float | None] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EditValidationError("The edit file must contain a JSON object.")

    _reject_unknown_fields(raw, _ROOT_FIELDS, "edit")

    version = raw.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise EditValidationError("version must be the integer 1.")

    output = _relative_output(raw.get("output"), project)

    clips_raw = raw.get("clips")
    if not isinstance(clips_raw, list):
        raise EditValidationError("clips must be an array.")

    clips = [
        _validate_clip(
            clip_raw,
            index,
            project,
            durations=durations,
        )
        for index, clip_raw in enumerate(clips_raw)
    ]

    return {
        "version": version,
        "output": output,
        "clips": clips,
    }


def _validate_clip(
    raw: Any,
    index: int,
    project: VideoProject,
    *,
    durations: Mapping[str, float | None] | None,
) -> dict[str, Any]:
    location = f"clips[{index}]"

    if not isinstance(raw, dict):
        raise EditValidationError(f"{location} must be an object.")

    future_fields = sorted(set(raw) & _FUTURE_CLIP_FIELDS)
    if future_fields:
        names = ", ".join(future_fields)
        raise EditValidationError(
            f"{location} uses properties not supported in version 1: {names}."
        )

    _reject_unknown_fields(raw, _CLIP_FIELDS, location)

    file_value = _relative_clip_path(raw.get("file"), location, project)
    start = _number(raw.get("start"), f"{location}.start")
    end = _number(raw.get("end"), f"{location}.end")

    if start < 0:
        raise EditValidationError(f"{location}.start must be zero or greater.")
    if end <= start:
        raise EditValidationError(
            f"{location}.end must be greater than {location}.start."
        )

    if durations is not None:
        duration = durations.get(file_value)
        if duration is not None and end > duration:
            raise EditValidationError(
                f"{location}.end exceeds the source duration for {file_value}."
            )

    label = raw.get("label")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise EditValidationError(
            f"{location}.label must be a non-empty string when provided."
        )

    result = {
        "file": file_value,
        "start": round(start, 3),
        "end": round(end, 3),
    }
    if label is not None:
        result["label"] = label

    return result


def _relative_clip_path(value: Any, location: str, project: VideoProject) -> str:
    relative = _relative_path(value, f"{location}.file")
    source = (project.clips_dir / relative).resolve()

    if not source.is_relative_to(project.clips_dir):
        raise EditValidationError(
            f"{location}.file must stay inside the project's clips directory."
        )
    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise EditValidationError(
            f"{location}.file is not a supported video type: {relative.as_posix()}"
        )
    if not source.is_file():
        raise EditValidationError(f"Source video does not exist: {source}")

    return source.relative_to(project.clips_dir).as_posix()


def _relative_output(value: Any, project: VideoProject) -> str:
    relative = _relative_path(value, "output")
    output = (project.exports_dir / relative).resolve()

    if not output.is_relative_to(project.exports_dir):
        raise EditValidationError(
            "output must stay inside the project's exports directory."
        )
    if output.suffix.lower() != ".mp4":
        raise EditValidationError("output must have an .mp4 extension.")

    return relative.as_posix()


def _relative_path(value: Any, location: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise EditValidationError(f"{location} must be a non-empty string.")

    path = Path(value)
    if path.is_absolute():
        raise EditValidationError(f"{location} must be a relative path.")

    return path


def _number(value: Any, location: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EditValidationError(f"{location} must be a number.")

    result = float(value)
    if not math.isfinite(result):
        raise EditValidationError(f"{location} must be a finite number.")

    return result


def _reject_unknown_fields(raw: dict, allowed: set[str], location: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise EditValidationError(f"Unknown properties in {location}: {names}.")