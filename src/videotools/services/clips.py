"""Read-only catalog using existing metadata and thumbnails."""
import math
from pathlib import Path
from urllib.parse import quote
from videotools.media import VIDEO_EXTENSIONS
from videotools.metadata import load_existing_report
from videotools.project import VideoProject
from videotools.thumbnails import thumbnail_name


def resolve_thumbnail(project: VideoProject, relative: str) -> Path:
    path = Path(relative.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in relative:
        raise ValueError("Invalid thumbnail path.")
    target = (project.metadata_dir / path).resolve()
    if not target.is_relative_to(project.metadata_dir):
        raise ValueError("Invalid thumbnail path.")
    if target.suffix.lower() not in {".webp", ".png", ".jpg", ".jpeg"} or not target.is_file():
        raise FileNotFoundError("Thumbnail not found.")
    return target


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0 else None


def _dimension(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def list_clips(project: VideoProject, project_id: str) -> list[dict]:
    try:
        report = load_existing_report(project.metadata_dir / "clip_report.json")
    except (OSError, ValueError, UnicodeError):
        report = {}
    entries = report.get("clips", []) if isinstance(report, dict) else []
    cached = {
        entry["relative_path"].replace("\\", "/"): entry
        for entry in entries if isinstance(entry, dict) and isinstance(entry.get("relative_path"), str)
    } if isinstance(entries, list) else {}
    clips = []
    for path in sorted(project.clips_dir.rglob("*")):
        if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
            continue
        if not path.resolve().is_relative_to(project.clips_dir):
            continue
        relative = path.relative_to(project.root).as_posix()
        entry = cached.get(relative, {})
        video = entry.get("video")
        video = video if isinstance(video, dict) else {}
        thumbnail = entry.get("thumbnail")
        candidates = []
        if isinstance(thumbnail, str):
            candidates.append(thumbnail.removeprefix("metadata/"))
            prefix = project.metadata_dir.relative_to(project.root).as_posix() + "/"
            if thumbnail.startswith(prefix):
                candidates.insert(0, thumbnail.removeprefix(prefix))
        candidates.append("thumbnails/" + thumbnail_name(path, project.root))
        thumbnail_url = None
        for candidate in candidates:
            try:
                target = resolve_thumbnail(project, candidate)
            except (ValueError, FileNotFoundError):
                continue
            encoded = quote(target.relative_to(project.metadata_dir).as_posix(), safe="/")
            thumbnail_url = f"/api/projects/{quote(project_id, safe='')}/thumbnails/{encoded}"
            break
        creation = entry.get("creation_time_local") or entry.get("creation_time")
        clips.append(dict(
            path=relative, name=path.name, duration=_number(entry.get("duration")),
            media_path=path.relative_to(project.clips_dir).as_posix(),
            width=_dimension(video.get("width")), height=_dimension(video.get("height")),
            fps=_number(video.get("fps")), creation_time=creation if isinstance(creation, str) else None,
            thumbnail_url=thumbnail_url,
        ))
    return clips

