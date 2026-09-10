from collections import Counter
from pathlib import Path

from videotools.journal import load_journal
from videotools.report import generate_html_report
from videotools.thumbnails import thumbnail_name
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import tomllib

from videotools.media import VIDEO_EXTENSIONS
import shutil
import subprocess
import json

from videotools.telemetry import (
    empty_gps,
    extract_gps,
    get_gopro_metadata_stream,
)



def parse_creation_time(
    value: str | None,
    timezone_name: str,
) -> datetime | None:
    if not value:
        return None

    # ffprobe gives us timestamps such as:
    # 2026-09-06T17:34:18.000000Z
    utc_time = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    local_timezone = ZoneInfo(timezone_name)

    return utc_time.astimezone(local_timezone)

def journal_entry_range(
    entry: dict,
    timezone_name: str,
):
    date_value = entry.get("date")
    start_time = entry.get("start_time")
    end_time = entry.get("end_time")

    if not date_value or not start_time:
        return None

    timezone = ZoneInfo(timezone_name)

    start = datetime.strptime(
        f"{date_value} {start_time}",
        "%Y-%m-%d %H:%M",
    ).replace(tzinfo=timezone)

    if end_time:
        end = datetime.strptime(
            f"{date_value} {end_time}",
            "%Y-%m-%d %H:%M",
        ).replace(tzinfo=timezone)

        # Support activities crossing midnight:
        # 23:00 -> 01:30
        if end < start:
            end += timedelta(days=1)
    else:
        end = None

    return start, end

def match_journal_entry(
    creation_time: str | None,
    journal: dict,
    timezone_name: str,
):
    clip_time = parse_creation_time(
        creation_time,
        timezone_name,
    )

    if clip_time is None:
        return None

    for entry in journal.get("entries", []):
        time_range = journal_entry_range(
            entry,
            timezone_name,
        )

        if time_range is None:
            continue

        start, end = time_range

        if end is None:
            # If only start time was given,
            # require same date and clip after start.
            if (
                clip_time.date() == start.date()
                and clip_time >= start
            ):
                return entry

        elif start <= clip_time <= end:
            return entry

    return None

def build_format_groups(report_clips):
    counter = Counter(
        (
            clip["video"]["width"],
            clip["video"]["height"],
            clip["video"]["fps"],
        )
        for clip in report_clips
    )

    groups = []

    for (width, height, fps), count in counter.most_common():
        groups.append(
            {
                "width": width,
                "height": height,
                "fps": fps,
                "count": count,
            }
        )

    return groups

def build_warnings(report_clips):
    warnings = []

    fps_groups = Counter(
        clip["video"]["fps"]
        for clip in report_clips
    )

    if len(fps_groups) > 1:
        warnings.append(
            {
                "type": "multiple_frame_rates",
                "message": "Multiple frame rates detected.",
                "values": dict(fps_groups),
            }
        )

    resolution_groups = Counter(
        (
            clip["video"]["width"],
            clip["video"]["height"],
        )
        for clip in report_clips
    )

    if len(resolution_groups) > 1:
        warnings.append(
            {
                "type": "multiple_resolutions",
                "message": "Multiple resolutions detected.",
                "values": [
                    {
                        "width": width,
                        "height": height,
                        "count": count,
                    }
                    for (width, height), count
                    in resolution_groups.items()
                ],
            }
        )

    return warnings

def parse_fps(value: str) -> float:
    if "/" in value:
        numerator, denominator = value.split("/")

        numerator = float(numerator)
        denominator = float(denominator)

        if denominator == 0:
            return 0.0

        return numerator / denominator

    return float(value)

def probe_video(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")

    if ffprobe is None:
        raise RuntimeError(
            "ffprobe was not found on PATH. "
            "Make sure FFmpeg is installed and ffprobe is accessible."
        )

    command = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return json.loads(result.stdout)

def most_common(values):
    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return None

    return Counter(values).most_common(1)[0][0]

def get_creation_time(info: dict):
    """
    Try to find the media creation timestamp reported by ffprobe.
    """

    format_tags = info.get("format", {}).get("tags", {})

    creation_time = format_tags.get("creation_time")

    if creation_time:
        return creation_time

    for stream in info.get("streams", []):
        tags = stream.get("tags", {})

        if tags.get("creation_time"):
            return tags["creation_time"]

    return None

def load_project_config(project_root: Path) -> dict:
    config_file = project_root / "project.toml"

    with config_file.open("rb") as file:
        return tomllib.load(file)

def load_existing_report(
    report_file: Path,
) -> dict | None:
    if not report_file.exists():
        return None

    try:
        return json.loads(
            report_file.read_text(
                encoding="utf-8",
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None

def analyze_project(
    project_root: Path,
    force: bool = False,
) -> dict:
    project_root = Path(project_root).resolve()

    config = load_project_config(project_root)

    timezone_name = config.get(
        "timezone",
        "Europe/Copenhagen",
    )

    clips_dir = project_root / "clips"
    metadata_dir = project_root / "metadata"

    report_file = metadata_dir / "clip_report.json"

    existing_report = (
        None
        if force
        else load_existing_report(report_file)
    )

    existing_clips = {}

    if existing_report:
        existing_clips = {
            clip["relative_path"]: clip
            for clip in existing_report.get(
                "clips",
                [],
            )
            if clip.get("relative_path")
        }

    html_report_file = metadata_dir / "clip_report.html"

    journal_file = project_root / "journal.json"
    journal = load_journal(journal_file)

    if not clips_dir.exists():
        raise RuntimeError(
            f"Clips directory does not exist: {clips_dir}"
        )

    metadata_dir.mkdir(exist_ok=True)

    # Recursive search so clips/20260907/*.MP4 also works.
    clips = sorted(
        path
        for path in clips_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not clips:
        raise RuntimeError(
            f"No video clips found in {clips_dir}"
        )

    report_clips = []

    for index, clip in enumerate(clips, start=1):
        relative_path = clip.relative_to(
            project_root
        ).as_posix()

        stat = clip.stat()

        existing_clip = existing_clips.get(
            relative_path
        )

        if (
            not force
            and existing_clip
            and existing_clip.get("size_bytes")
            == stat.st_size
            and existing_clip.get("modified_time_ns")
            == stat.st_mtime_ns
        ):
            print(
                f"[{index}/{len(clips)}] "
                f"Unchanged {clip.name}"
            )

            thumbnail_filename = thumbnail_name(
                clip,
                project_root,
            )

            thumbnail_file = (
                project_root
                / "metadata"
                / "thumbnails"
                / thumbnail_filename
            )

            cached_clip = existing_clip.copy()

            cached_clip["thumbnail"] = (
                f"metadata/thumbnails/{thumbnail_filename}"
                if thumbnail_file.exists()
                else None
            )

            report_clips.append(cached_clip)

            continue

        print(
            f"[{index}/{len(clips)}] "
            f"Probing {clip.name}"
        )

        try:
            info = probe_video(clip)

            gopro_metadata_stream = get_gopro_metadata_stream(
                info
            )

            if gopro_metadata_stream:
                gps = extract_gps(clip)
            else:
                gps = empty_gps()
        except subprocess.CalledProcessError as error:
            print(f"WARNING: ffprobe failed for {clip}")
            print(error.stderr)
            continue

        video_stream = next(
            (
                stream
                for stream in info.get("streams", [])
                if stream.get("codec_type") == "video"
            ),
            None,
        )

        audio_stream = next(
            (
                stream
                for stream in info.get("streams", [])
                if stream.get("codec_type") == "audio"
            ),
            None,
        )

        if video_stream is None:
            print(f"Skipping {clip.name}: no video stream")
            continue

        fps = parse_fps(
            video_stream.get("avg_frame_rate", "0/1")
        )

        format_info = info.get("format", {})

        duration = float(
            format_info.get("duration") or 0
        )

        file_size = int(
            format_info.get("size") or clip.stat().st_size
        )

        bitrate = int(
            format_info.get("bit_rate") or 0
        )

        creation_time = get_creation_time(info)

        matched_journal = match_journal_entry(
            creation_time,
            journal,
            timezone_name,
        )

        local_creation_time = parse_creation_time(
            creation_time,
            timezone_name,
        )

        thumbnail_filename = thumbnail_name(
            clip,
            project_root,
        )

        thumbnail_file = (
            project_root
            / "metadata"
            / "thumbnails"
            / thumbnail_filename
        )

        clip_info = {
            "name": clip.name,


            "relative_path": relative_path,
            "thumbnail": (
                f"metadata/thumbnails/{thumbnail_filename}"
                if thumbnail_file.exists()
                else None
            ),
            "size_bytes": file_size,
            "modified_time_ns": clip.stat().st_mtime_ns,
            "creation_time": creation_time,

            "creation_time_local": (
                local_creation_time.isoformat()
                if local_creation_time
                else None
            ),

            "duration": round(duration, 3),

            "video": {
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": round(fps, 3),
                "codec": video_stream.get("codec_name"),
                "profile": video_stream.get("profile"),
                "pixel_format": video_stream.get("pix_fmt"),
                "bitrate": bitrate,
            },

            "audio": None,
            "telemetry": {
                "gopro_metadata": (
                    gopro_metadata_stream is not None
                ),
                "gps": gps,
            },
            "journal": None,
        }

        if matched_journal:
            clip_info["journal"] = {
                "date": matched_journal.get("date"),
                "activity": matched_journal.get("activity"),
                "location": matched_journal.get("location"),
                "start_time": matched_journal.get("start_time"),
                "end_time": matched_journal.get("end_time"),
                "tags": matched_journal.get("tags", []),
                "highlight": matched_journal.get("highlight"),
            }

        if audio_stream:
            clip_info["audio"] = {
                "codec": audio_stream.get("codec_name"),
                "sample_rate": audio_stream.get("sample_rate"),
                "channels": audio_stream.get("channels"),
                "channel_layout": audio_stream.get(
                    "channel_layout"
                ),
            }

        report_clips.append(clip_info)

    if not report_clips:
        raise RuntimeError(
            "No usable video clips found."
        )

    widths = [
        clip["video"]["width"]
        for clip in report_clips
    ]

    heights = [
        clip["video"]["height"]
        for clip in report_clips
    ]

    fps_values = [
        clip["video"]["fps"]
        for clip in report_clips
    ]

    total_duration = sum(
        clip["duration"]
        for clip in report_clips
    )

    total_size = sum(
        clip["size_bytes"]
        for clip in report_clips
    )

    format_groups = build_format_groups(report_clips)
    warnings = build_warnings(report_clips)

    report = {
        "summary": {
            "clip_count": len(report_clips),
            "total_duration_seconds": round(
                total_duration,
                3,
            ),
            "total_size_bytes": total_size,
            "recommended_width": most_common(widths),
            "recommended_height": most_common(heights),
            "recommended_fps": most_common(fps_values),
            "formats": format_groups,
            "warnings": warnings,
        },
        "clips": report_clips,
    }

    report_file.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    generate_html_report(
        report,
        html_report_file,
        journal,
    )

    print()
    print("=" * 60)
    print("CLIP REPORT CREATED")
    print("=" * 60)

    print(f"Clips:      {len(report_clips)}")
    print(
        f"Resolution: "
        f"{report['summary']['recommended_width']}x"
        f"{report['summary']['recommended_height']}"
    )
    print(
        f"FPS:        "
        f"{report['summary']['recommended_fps']}"
    )

    print()
    print("FORMATS")
    print("-" * 60)

    for group in format_groups:
        print(
            f"{group['count']:>3} clip(s)  "
            f"{group['width']}x{group['height']}  "
            f"{group['fps']} fps"
        )

    if warnings:
        print()
        print("WARNINGS")
        print("-" * 60)

        for warning in warnings:
            print(f"- {warning['message']}")


    print()
    print("Written to:")
    print(report_file)
    print(html_report_file)

    return report