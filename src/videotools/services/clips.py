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


def _journal_match(value):
    if not isinstance(value, dict):
        return None

    tags = value.get("tags")
    if isinstance(tags, list):
        cleaned_tags = [str(tag) for tag in tags if str(tag).strip()]
    else:
        cleaned_tags = []

    return {
        "date": value.get("date") if isinstance(value.get("date"), str) else None,
        "activity": value.get("activity") if isinstance(value.get("activity"), str) else None,
        "location": value.get("location") if isinstance(value.get("location"), str) else None,
        "start_time": value.get("start_time") if isinstance(value.get("start_time"), str) else None,
        "end_time": value.get("end_time") if isinstance(value.get("end_time"), str) else None,
        "tags": cleaned_tags,
        "highlight": value.get("highlight") if isinstance(value.get("highlight"), str) else None,
    }


def _gps_match(value):
    if not isinstance(value, dict):
        return None

    available = bool(value.get("available"))

    def float_or_none(name):
        raw = value.get(name)
        return raw if isinstance(raw, (int, float)) and not isinstance(raw, bool) else None

    return {
        "available": available,
        "latitude": float_or_none("latitude"),
        "longitude": float_or_none("longitude"),
        "altitude": float_or_none("altitude"),
        "speed": float_or_none("speed"),
        "datetime": value.get("datetime") if isinstance(value.get("datetime"), str) else None,
    }


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
        telemetry = entry.get("telemetry")
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        clips.append(dict(
            path=relative, name=path.name, duration=_number(entry.get("duration")),
            media_path=path.relative_to(project.clips_dir).as_posix(),
            width=_dimension(video.get("width")), height=_dimension(video.get("height")),
            fps=_number(video.get("fps")), creation_time=creation if isinstance(creation, str) else None,
            thumbnail_url=thumbnail_url,
            journal=_journal_match(entry.get("journal")),
            gps=_gps_match(telemetry.get("gps")),
        ))
    return clips

