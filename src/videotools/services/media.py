from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject

STREAM_CHUNK_SIZE = 256 * 1024


def resolve_project_media(project: VideoProject, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or ":" in normalized:
        raise ValueError("Media path must stay inside the project's clips directory.")

    root = project.clips_dir.resolve()
    target = (root / candidate).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Media path must stay inside the project's clips directory.")
    if target.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError("Media path is not a supported video type.")
    if not target.is_file():
        raise FileNotFoundError(f"Media file does not exist: {target}")
    return target


def resolve_export_video(
    project: VideoProject,
    filename: str,
    *,
    social: bool = False,
) -> Path:
    value = filename.strip()
    candidate = Path(value)
    root = (project.exports_social_dir if social else project.exports_dir).resolve()
    root_name = "exports-social" if social else "exports"

    if not value:
        raise ValueError("Export filename is required.")
    if candidate.is_absolute() or ".." in candidate.parts or ":" in value:
        raise ValueError(f"Export filename must stay inside the project's {root_name} directory.")
    if "/" in value or "\\" in value or len(candidate.parts) != 1:
        raise ValueError("Export filename must not include directory separators.")
    if candidate.suffix.lower() != ".mp4":
        raise ValueError("Export filename must use the .mp4 extension.")

    target = (root / candidate.name).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Export filename must stay inside the project's {root_name} directory.")
    if not target.is_file():
        raise FileNotFoundError("Export file was not found.")
    return target


def parse_byte_range(value: str, file_size: int) -> tuple[int | None, int | None]:
    if not value.startswith("bytes=") or "," in value:
        return None, None

    start_text, _, end_text = value.removeprefix("bytes=").partition("-")
    try:
        if start_text and end_text:
            start, end = int(start_text), int(end_text)
        elif start_text:
            start, end = int(start_text), file_size - 1
        elif end_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None, None
            start, end = max(0, file_size - suffix_length), file_size - 1
        else:
            return None, None
    except ValueError:
        return None, None

    if start < 0 or end < start or start >= file_size:
        return None, None
    return start, min(end, file_size - 1)


def stream_file(path: Path, *, start: int, length: int) -> Iterator[bytes]:
    remaining = length
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
