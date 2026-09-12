"""JSON edit-timeline model and validation."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject


class EditValidationError(ValueError):
    """Raised when an edit JSON file is invalid."""


@dataclass(frozen=True)
class EditClip:
    file: Path
    start: float
    end: float
    label: str | None = None

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class EditTimeline:
    output: Path
    clips: tuple[EditClip, ...]
    version: int = 1


_ROOT_FIELDS = {"version", "output", "clips"}
_CLIP_FIELDS = {"file", "start", "end", "label"}
_FUTURE_CLIP_FIELDS = {
    "speed",
    "volume",
    "fade_in",
    "fade_out",
}


def load_edit_timeline(
    edit_file: Path,
    project: VideoProject,
) -> EditTimeline:
    """Load and validate a version-1 edit timeline."""

    edit_file = Path(edit_file).resolve()

    try:
        raw = json.loads(edit_file.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise EditValidationError(
            f"Edit file does not exist: {edit_file}"
        ) from error
    except OSError as error:
        raise EditValidationError(
            f"Could not read edit file {edit_file}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise EditValidationError(
            f"Invalid JSON in {edit_file}: "
            f"line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error

    return parse_edit_timeline(raw, project)


def parse_edit_timeline(
    raw: Any,
    project: VideoProject,
) -> EditTimeline:
    if not isinstance(raw, dict):
        raise EditValidationError("The edit file must contain a JSON object.")

    _reject_unknown_fields(raw, _ROOT_FIELDS, "edit")

    version = raw.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int):
        raise EditValidationError("version must be the integer 1.")
    if version != 1:
        raise EditValidationError(
            f"Unsupported edit-file version {version}; only version 1 is supported."
        )

    output = _resolve_output(raw.get("output"), project)

    clips_raw = raw.get("clips")
    if not isinstance(clips_raw, list) or not clips_raw:
        raise EditValidationError("clips must be a non-empty array.")

    clips = tuple(
        _parse_clip(clip_raw, index, project)
        for index, clip_raw in enumerate(clips_raw)
    )

    return EditTimeline(
        output=output,
        clips=clips,
        version=version,
    )


def _parse_clip(
    raw: Any,
    index: int,
    project: VideoProject,
) -> EditClip:
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

    source = _resolve_source(raw.get("file"), location, project)
    start = _number(raw.get("start"), f"{location}.start")
    end = _number(raw.get("end"), f"{location}.end")

    if start < 0:
        raise EditValidationError(f"{location}.start must be zero or greater.")
    if end <= start:
        raise EditValidationError(
            f"{location}.end must be greater than {location}.start."
        )

    label = raw.get("label")
    if label is not None and (not isinstance(label, str) or not label.strip()):
        raise EditValidationError(
            f"{location}.label must be a non-empty string when provided."
        )

    return EditClip(
        file=source,
        start=start,
        end=end,
        label=label,
    )


def _resolve_source(
    value: Any,
    location: str,
    project: VideoProject,
) -> Path:
    relative = _relative_path(value, f"{location}.file")
    source = (project.clips_dir / relative).resolve()

    if not source.is_relative_to(project.clips_dir):
        raise EditValidationError(
            f"{location}.file must stay inside the project's clips directory."
        )
    if source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise EditValidationError(
            f"{location}.file is not a supported video type: {relative}"
        )
    if not source.is_file():
        raise EditValidationError(f"Source video does not exist: {source}")

    return source


def _resolve_output(value: Any, project: VideoProject) -> Path:
    relative = _relative_path(value, "output")
    output = (project.exports_dir / relative).resolve()

    if not output.is_relative_to(project.exports_dir):
        raise EditValidationError(
            "output must stay inside the project's exports directory."
        )
    if output.suffix.lower() != ".mp4":
        raise EditValidationError("output must have an .mp4 extension.")

    return output


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


def _reject_unknown_fields(
    raw: dict,
    allowed: set[str],
    location: str,
) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise EditValidationError(f"Unknown properties in {location}: {names}.")
