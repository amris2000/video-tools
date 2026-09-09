from collections import Counter
from pathlib import Path
import json
import shutil
import subprocess
from html import escape
from videotools.journal import load_journal
from videotools.thumbnails import thumbnail_name
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import tomllib

from math import asin, cos, isfinite, radians, sin, sqrt
from statistics import median

from videotools.media import VIDEO_EXTENSIONS
import shutil
import subprocess
import json

def empty_gps() -> dict:
    return {
        "available": False,
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "speed": None,
        "datetime": None,
        "samples_total": 0,
        "samples_valid": 0,
        "samples_rejected": 0,
    }

MAX_GPS_SPEED_KMH = 250.0
MAX_GPS_POSITION_ERROR = 500.0


def parse_optional_float(value: str) -> float | None:
    value = value.strip()

    if not value or value == "-":
        return None

    try:
        number = float(value)
    except ValueError:
        return None

    if not isfinite(number):
        return None

    return number


def haversine_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    earth_radius_m = 6_371_000

    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        sin(delta_lat / 2) ** 2
        + cos(lat1_rad)
        * cos(lat2_rad)
        * sin(delta_lon / 2) ** 2
    )

    return (
        2
        * earth_radius_m
        * asin(sqrt(a))
    )

def get_gopro_metadata_stream(info: dict) -> dict | None:
    return next(
        (
            stream
            for stream in info.get("streams", [])
            if (
                stream.get("codec_type") == "data"
                and stream.get("codec_tag_string") == "gpmd"
            )
        ),
        None,
    )


def extract_gps(path: Path) -> dict:
    exiftool = shutil.which("exiftool")

    if exiftool is None:
        print("  GPS: ExifTool not found on PATH")
        return empty_gps()

    command = [
        exiftool,
        "-ee",
        "-n",
        "-f",
        "-p",
        (
            "${GPSLatitude#}\t"
            "${GPSLongitude#}\t"
            "${GPSAltitude#}\t"
            "${GPSSpeed#}\t"
            "${GPSDateTime}\t"
            "${GPSMeasureMode#}\t"
            "${GPSHPositioningError#}"
        ),
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return empty_gps()

    samples = []

    for line in result.stdout.splitlines():
        parts = line.split("\t")

        if len(parts) != 7:
            continue

        (
            latitude_raw,
            longitude_raw,
            altitude_raw,
            speed_raw,
            datetime_raw,
            measure_mode_raw,
            position_error_raw,
        ) = parts

        latitude = parse_optional_float(latitude_raw)
        longitude = parse_optional_float(longitude_raw)
        altitude = parse_optional_float(altitude_raw)
        speed = parse_optional_float(speed_raw)
        measure_mode = parse_optional_float(
            measure_mode_raw
        )
        position_error = parse_optional_float(
            position_error_raw
        )

        if latitude is None or longitude is None:
            continue

        samples.append(
            {
                "latitude": latitude,
                "longitude": longitude,
                "altitude": altitude,
                "speed": speed,
                "datetime": (
                    None
                    if datetime_raw.strip() in {"", "-"}
                    else datetime_raw.strip()
                ),
                "measure_mode": measure_mode,
                "position_error": position_error,
            }
        )

    if not samples:
        return empty_gps()

    valid_samples = []

    for sample in samples:
        latitude = sample["latitude"]
        longitude = sample["longitude"]
        speed = sample["speed"]
        measure_mode = sample["measure_mode"]
        position_error = sample["position_error"]

        # Basic coordinate sanity.
        if not (-90 <= latitude <= 90):
            continue

        if not (-180 <= longitude <= 180):
            continue

        # GoPro GPS fix:
        # 0 = no lock
        # 2 = 2D lock
        # 3 = 3D lock
        if (
            measure_mode is not None
            and measure_mode not in {2, 3}
        ):
            continue

        # GoPro documents GPS precision below 500
        # as a good fix.
        if (
            position_error is not None
            and position_error > MAX_GPS_POSITION_ERROR
        ):
            continue

        # Reject physically implausible speed for our
        # normal video workflow.
        if (
            speed is not None
            and (
                speed < 0
                or speed > MAX_GPS_SPEED_KMH
            )
        ):
            continue

        valid_samples.append(sample)

    if not valid_samples:
        result = empty_gps()

        result["samples_total"] = len(samples)
        result["samples_rejected"] = len(samples)

        return result

    #
    # Use the median instead of the first GPS point.
    #
    # Median is deliberately used because a handful of
    # bad coordinates won't drag the representative
    # position away from the main cluster.
    #

    latitude = median(
        sample["latitude"]
        for sample in valid_samples
    )

    longitude = median(
        sample["longitude"]
        for sample in valid_samples
    )

    #
    # Find the real GPS sample closest to our median
    # coordinate. This gives altitude/speed/time that
    # correspond to an actual measurement instead of
    # mixing independent median values.
    #

    representative_sample = min(
        valid_samples,
        key=lambda sample: haversine_distance_m(
            latitude,
            longitude,
            sample["latitude"],
            sample["longitude"],
        ),
    )

    altitude = representative_sample["altitude"]

    # Altitude can be independently corrupt even when
    # latitude/longitude look reasonable. Don't reject
    # the whole GPS point because of it.
    if (
        altitude is not None
        and not (-500 <= altitude <= 9000)
    ):
        altitude = None

    return {
        "available": True,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "speed": representative_sample["speed"],
        "datetime": representative_sample["datetime"],
        "samples_total": len(samples),
        "samples_valid": len(valid_samples),
        "samples_rejected": (
            len(samples) - len(valid_samples)
        ),
    }

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




def format_duration(seconds: float) -> str:
    total_seconds = int(round(seconds))

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


def generate_html_report(
    report: dict,
    output_file: Path,
    journal: dict | None = None,
):
    clips = report["clips"]
    summary = report["summary"]

    grouped = {}

    for clip in clips:
        relative_path = Path(clip["relative_path"])

        parts = relative_path.parts

        date_folder = "Unknown"

        if len(parts) >= 3:
            date_folder = parts[1]

        grouped.setdefault(date_folder, []).append(clip)

    sections = []

    journal = journal or {"entries": []}

    journal_by_date = {}

    for entry in journal.get("entries", []):
        date_value = entry.get("date")

        if not date_value:
            continue

        # 2026-09-06 -> 20260906
        date_key = date_value.replace("-", "")

        journal_by_date.setdefault(
            date_key,
            [],
        ).append(entry)

    for date_folder, date_clips in sorted(grouped.items()):
        day_journal_entries = journal_by_date.get(
            date_folder,
            [],
        )

        journal_cards = []

        for entry in day_journal_entries:
            activity = escape(
                entry.get("activity") or "Untitled activity"
            )

            location = escape(
                entry.get("location") or ""
            )

            start_time = entry.get("start_time")
            end_time = entry.get("end_time")

            time_text = ""

            if start_time and end_time:
                time_text = f"{start_time}–{end_time}"
            elif start_time:
                time_text = start_time

            tags = entry.get("tags", [])

            tags_html = "".join(
                f'<span class="tag">{escape(tag)}</span>'
                for tag in tags
            )

            highlight = escape(
                entry.get("highlight") or ""
            )

            notes = escape(
                entry.get("notes") or ""
            )

            journal_cards.append(
                f"""
                <div class="journal-card">
                    <div class="journal-heading">
                        <h3>{activity}</h3>
                        <span class="journal-time">
                            {escape(time_text)}
                        </span>
                    </div>

                    {
                        f'<div class="journal-location">{location}</div>'
                        if location
                        else ''
                    }

                    {
                        f'<div class="tags">{tags_html}</div>'
                        if tags
                        else ''
                    }

                    {
                        f'''
                        <div class="journal-highlight">
                            <strong>Highlight:</strong>
                            {highlight}
                        </div>
                        '''
                        if highlight
                        else ''
                    }

                    {
                        f'''
                        <div class="journal-notes">
                            {notes}
                        </div>
                        '''
                        if notes
                        else ''
                    }
                </div>
                """
            )

        journal_html = ""

        if journal_cards:
            journal_html = f"""
            <div class="journal-section">
                {''.join(journal_cards)}
            </div>
            """

        cards = []

        for clip in date_clips:
            video = clip["video"]
            audio = clip.get("audio")

            fps = video["fps"]

            high_frame_rate = fps >= 60

            badge = ""

            if high_frame_rate:
                badge = """
                <span class="badge">HIGH FRAME RATE</span>
                """

            creation_time = (
                clip.get("creation_time_local")
                or clip.get("creation_time")
                or "Unknown"
            )

            thumbnail = clip.get("thumbnail")

            thumbnail_html = ""

            if thumbnail:
                thumbnail_relative = Path(
                    thumbnail
                ).relative_to("metadata")

                thumbnail_html = f"""
                <img
                    class="clip-thumbnail"
                    src="{escape(thumbnail_relative.as_posix())}"
                    alt="{escape(clip["name"])}"
                    loading="lazy"
                >
                """

            audio_text = "No audio"

            if audio:
                audio_text = (
                    f'{audio.get("codec", "?").upper()} · '
                    f'{audio.get("sample_rate", "?")} Hz · '
                    f'{audio.get("channels", "?")} ch'
                )

            matched_entry = clip.get("journal")

            journal_match_html = ""

            if matched_entry:
                journal_match_html = f"""
                <div class="clip-journal">
                    <strong>
                        {escape(
                            matched_entry.get("activity")
                            or "Journal activity"
                        )}
                    </strong>

                    <div>
                        {escape(
                            matched_entry.get("location")
                            or ""
                        )}
                    </div>
                </div>
                """

            cards.append(
                f"""
                <article class="clip-card">
                    {thumbnail_html}
                    <div class="clip-header">
                        <div>
                            <h3>{escape(clip["name"])}</h3>
                            <div class="path">
                                {escape(clip["relative_path"])}
                            </div>
                        </div>

                        {badge}
                    </div>

                    <div class="stats">
                        <div>
                            <span class="label">Duration</span>
                            <span>
                                {format_duration(clip["duration"])}
                            </span>
                        </div>

                        <div>
                            <span class="label">Resolution</span>
                            <span>
                                {video["width"]} × {video["height"]}
                            </span>
                        </div>

                        <div>
                            <span class="label">Frame rate</span>
                            <span>
                                {fps} fps
                            </span>
                        </div>

                        <div>
                            <span class="label">Codec</span>
                            <span>
                                {escape(str(video["codec"]).upper())}
                            </span>
                        </div>
                    </div>
                    {journal_match_html}
                    <div class="details">
                        <div>
                            <strong>Created:</strong>
                            {escape(creation_time)}
                        </div>

                        <div>
                            <strong>Audio:</strong>
                            {escape(audio_text)}
                        </div>

                        <div>
                            <strong>Pixel format:</strong>
                            {escape(str(video.get("pixel_format")))}
                        </div>
                    </div>
                </article>
                """
            )

        sections.append(
            f"""
            <section class="day-section">
                <h2>{escape(date_folder)}</h2>

                {journal_html}

                <div class="clip-grid">
                    {''.join(cards)}
                </div>
            </section>
            """
        )

    format_rows = []

    for group in summary.get("formats", []):
        format_rows.append(
            f"""
            <tr>
                <td>{group["count"]}</td>
                <td>{group["width"]} × {group["height"]}</td>
                <td>{group["fps"]} fps</td>
            </tr>
            """
        )

    warnings_html = ""

    warnings = summary.get("warnings", [])

    if warnings:
        warning_items = "".join(
            f"<li>{escape(warning['message'])}</li>"
            for warning in warnings
        )

        warnings_html = f"""
        <section class="warnings">
            <h2>Warnings</h2>
            <ul>
                {warning_items}
            </ul>
        </section>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Clip Report</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family:
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
            background: #f4f5f7;
            color: #1f2937;
        }}

        .container {{
            width: min(1200px, 92%);
            margin: 0 auto;
            padding: 40px 0 80px;
        }}

        header {{
            margin-bottom: 32px;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: 2.2rem;
        }}

        .subtitle {{
            color: #6b7280;
        }}

        .clip-thumbnail {{
            display: block;
            width: 100%;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            border-radius: 10px;
            margin-bottom: 16px;
            background: #e5e7eb;
        }}

        .summary {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin: 28px 0;
        }}

        .summary-card {{
            background: white;
            border-radius: 12px;
            padding: 18px;
            box-shadow:
                0 1px 3px rgba(0, 0, 0, 0.08);
        }}

        .summary-card .label {{
            display: block;
            color: #6b7280;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
        }}

        .summary-card .value {{
            font-size: 1.3rem;
            font-weight: 700;
        }}



        .format-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
            background: white;
            border-radius: 12px;
            overflow: hidden;
            box-shadow:
                0 1px 3px rgba(0, 0, 0, 0.08);
        }}

        .format-table th,
        .format-table td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}

        .format-table th {{
            background: #f9fafb;
        }}

        .warnings {{
            margin: 28px 0;
            padding: 18px 22px;
            background: #fff7ed;
            border-left: 4px solid #f97316;
            border-radius: 8px;
        }}

        .warnings h2 {{
            margin-top: 0;
        }}

        .day-section {{
            margin-top: 42px;
        }}

        .day-section h2 {{
            margin-bottom: 16px;
            font-size: 1.5rem;
        }}

        .clip-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(320px, 1fr));
            gap: 18px;
        }}

        .clip-card {{
            background: white;
            border-radius: 14px;
            padding: 20px;
            box-shadow:
                0 2px 8px rgba(0, 0, 0, 0.07);
        }}

        .clip-header {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: flex-start;
        }}

        .clip-header h3 {{
            margin: 0 0 4px;
            font-size: 1.05rem;
        }}

        .clip-journal {{
            margin-top: 14px;
            padding: 10px 12px;
            background: #eef2ff;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #3730a3;
        }}

        .path {{
            color: #6b7280;
            font-size: 0.8rem;
            word-break: break-all;
        }}

        .badge {{
            flex-shrink: 0;
            background: #111827;
            color: white;
            font-size: 0.7rem;
            font-weight: 700;
            padding: 6px 8px;
            border-radius: 999px;
            letter-spacing: 0.04em;
        }}

        .stats {{
            display: grid;
            grid-template-columns:
                repeat(2, minmax(0, 1fr));
            gap: 12px;
            margin-top: 18px;
        }}

        .stats > div {{
            padding: 10px;
            background: #f9fafb;
            border-radius: 8px;
        }}

        .stats .label {{
            display: block;
            color: #6b7280;
            font-size: 0.75rem;
            margin-bottom: 3px;
        }}

        .details {{
            margin-top: 16px;
            color: #4b5563;
            font-size: 0.88rem;
            line-height: 1.6;
        }}

        .journal-section {{
            margin-bottom: 20px;
        }}

        .journal-card {{
            background: #eef2ff;
            border-left: 4px solid #6366f1;
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 14px;
        }}

        .journal-heading {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: baseline;
        }}

        .journal-heading h3 {{
            margin: 0;
        }}

        .journal-time {{
            color: #4f46e5;
            font-weight: 600;
            white-space: nowrap;
        }}

        .journal-location {{
            margin-top: 4px;
            color: #6b7280;
        }}

        .tags {{
            margin-top: 12px;
        }}

        .tag {{
            display: inline-block;
            background: white;
            border-radius: 999px;
            padding: 4px 9px;
            margin-right: 6px;
            margin-bottom: 4px;
            font-size: 0.78rem;
        }}

        .journal-highlight {{
            margin-top: 12px;
        }}

        .journal-notes {{
            margin-top: 8px;
            color: #4b5563;
        }}
        
        @media (max-width: 600px) {{
            .container {{
                width: 94%;
                padding-top: 24px;
            }}

            .stats {{
                grid-template-columns: 1fr;
            }}

            .clip-header {{
                flex-direction: column;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">

        <header>
            <h1>Clip Report</h1>
            <div class="subtitle">
                Generated by video-tools
            </div>
        </header>

        <section class="summary">
            <div class="summary-card">
                <span class="label">Clips</span>
                <span class="value">
                    {summary["clip_count"]}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Total duration</span>
                <span class="value">
                    {format_duration(
                        summary["total_duration_seconds"]
                    )}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Resolution</span>
                <span class="value">
                    {summary["recommended_width"]}
                    ×
                    {summary["recommended_height"]}
                </span>
            </div>

            <div class="summary-card">
                <span class="label">Default FPS</span>
                <span class="value">
                    {summary["recommended_fps"]}
                </span>
            </div>
        </section>

        <section>
            <h2>Formats</h2>

            <table class="format-table">
                <thead>
                    <tr>
                        <th>Clips</th>
                        <th>Resolution</th>
                        <th>Frame rate</th>
                    </tr>
                </thead>

                <tbody>
                    {''.join(format_rows)}
                </tbody>
            </table>
        </section>

        {warnings_html}

        {''.join(sections)}

    </div>
</body>
</html>
"""

    output_file.write_text(
        html,
        encoding="utf-8",
    )

def load_project_config(project_root: Path) -> dict:
    config_file = project_root / "project.toml"

    with config_file.open("rb") as file:
        return tomllib.load(file)

def analyze_project(project_root: Path) -> dict:
    project_root = Path(project_root).resolve()

    config = load_project_config(project_root)

    timezone_name = config.get(
        "timezone",
        "Europe/Copenhagen",
    )

    clips_dir = project_root / "clips"
    metadata_dir = project_root / "metadata"

    report_file = metadata_dir / "clip_report.json"
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
        print(f"[{index}/{len(clips)}] Probing {clip.name}")

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


            "relative_path": clip.relative_to(
                project_root
            ).as_posix(),
            "thumbnail": (
                f"metadata/thumbnails/{thumbnail_filename}"
                if thumbnail_file.exists()
                else None
            ),
            "size_bytes": file_size,

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