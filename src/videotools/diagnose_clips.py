from pathlib import Path

import json
import shutil
import subprocess

from collections import Counter


PROJECT_DIR = Path(
    r"C:\Users\Frederik\Videos\Projects\first-video-test"
)

CLIPS_DIR = PROJECT_DIR / "clips"

REPORT_FILE = PROJECT_DIR / "clip_report.json"

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".m4v",
}


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
    command = [
        "ffprobe",
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


def empty_gps() -> dict:
    """
    Return a predictable GPS structure when
    no usable GPS information is available.
    """
    return {
        "available": False,
        "latitude": None,
        "longitude": None,
        "altitude": None,
        "speed": None,
        "datetime": None,
    }


def extract_gps(path: Path) -> dict:
    """
    Extract a representative GPS position from
    GoPro metadata using ExifTool.

    If ExifTool is unavailable, GPS isn't present,
    or extraction fails, return an empty GPS object.
    """

    exiftool = shutil.which("exiftool")

    if exiftool is None:
        return empty_gps()

    command = [
        exiftool,
        "-j",

        # Return raw numerical coordinates instead
        # of formatted degrees/minutes/seconds.
        "-n",

        # Extract embedded telemetry from video.
        "-ee",

        "-GPSLatitude",
        "-GPSLongitude",
        "-GPSAltitude",
        "-GPSSpeed",
        "-GPSDateTime",

        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

        data = json.loads(result.stdout)

    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ):
        return empty_gps()

    if not data:
        return empty_gps()

    metadata = data[0]

    latitude = metadata.get("GPSLatitude")
    longitude = metadata.get("GPSLongitude")

    # We consider GPS usable only if both coordinates exist.
    if latitude is None or longitude is None:
        return empty_gps()

    return {
        "available": True,
        "latitude": latitude,
        "longitude": longitude,
        "altitude": metadata.get("GPSAltitude"),
        "speed": metadata.get("GPSSpeed"),
        "datetime": metadata.get("GPSDateTime"),
    }


def get_gopro_metadata_stream(info: dict) -> dict | None:
    """
    Find the GoPro GPMF telemetry stream reported
    by ffprobe.
    """

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


def most_common(values):
    if not values:
        return None

    return Counter(values).most_common(1)[0][0]


def main():
    # Scan recursively because clips may live in folders
    # such as clips/20260906/.
    clips = sorted(
        path
        for path in CLIPS_DIR.rglob("*")
        if (
            path.is_file()
            and path.suffix.lower() in VIDEO_EXTENSIONS
        )
    )

    if not clips:
        raise RuntimeError("No clips found.")

    report_clips = []

    for index, clip in enumerate(
        clips,
        start=1,
    ):
        print(
            f"[{index}/{len(clips)}] "
            f"{clip.name}"
        )

        info = probe_video(clip)

        video_stream = next(
            (
                stream
                for stream in info["streams"]
                if stream.get("codec_type") == "video"
            ),
            None,
        )

        audio_stream = next(
            (
                stream
                for stream in info["streams"]
                if stream.get("codec_type") == "audio"
            ),
            None,
        )

        gopro_metadata_stream = get_gopro_metadata_stream(
            info
        )

        if video_stream is None:
            print(
                f"  Skipping {clip.name}: "
                "no video stream"
            )
            continue

        fps = parse_fps(
            video_stream.get(
                "avg_frame_rate",
                "0/1",
            )
        )

        duration = float(
            info.get(
                "format",
                {},
            ).get(
                "duration",
                0,
            )
        )

        # Only ask ExifTool for GPS when ffprobe tells
        # us this is a GoPro telemetry-bearing file.
        if gopro_metadata_stream:
            gps = extract_gps(clip)
        else:
            gps = empty_gps()

        clip_info = {
            "name": clip.name,

            # Portable path relative to project.
            "relative_path": clip.relative_to(
                PROJECT_DIR
            ).as_posix(),

            "width": video_stream.get("width"),
            "height": video_stream.get("height"),

            "fps": round(
                fps,
                3,
            ),

            "codec": video_stream.get(
                "codec_name"
            ),

            "pixel_format": video_stream.get(
                "pix_fmt"
            ),

            "duration": round(
                duration,
                3,
            ),

            "audio": None,

            "telemetry": {
                "gopro_metadata": (
                    gopro_metadata_stream is not None
                ),
                "gps": gps,
            },
        }

        if audio_stream:
            clip_info["audio"] = {
                "codec": audio_stream.get(
                    "codec_name"
                ),
                "sample_rate": audio_stream.get(
                    "sample_rate"
                ),
                "channels": audio_stream.get(
                    "channels"
                ),
            }

        report_clips.append(
            clip_info
        )

        if gps["available"]:
            print(
                f"  GPS: "
                f"{gps['latitude']}, "
                f"{gps['longitude']}"
            )

        elif gopro_metadata_stream:
            print(
                "  GPS: no usable GPS position found"
            )

        else:
            print(
                "  GPS: no GoPro telemetry stream"
            )

    if not report_clips:
        raise RuntimeError(
            "No usable video clips found."
        )

    widths = [
        clip["width"]
        for clip in report_clips
    ]

    heights = [
        clip["height"]
        for clip in report_clips
    ]

    fps_values = [
        clip["fps"]
        for clip in report_clips
    ]

    recommended_width = most_common(
        widths
    )

    recommended_height = most_common(
        heights
    )

    recommended_fps = most_common(
        fps_values
    )

    gps_clip_count = sum(
        1
        for clip in report_clips
        if clip["telemetry"]["gps"]["available"]
    )

    report = {
        "summary": {
            "clip_count": len(
                report_clips
            ),
            "recommended_width": (
                recommended_width
            ),
            "recommended_height": (
                recommended_height
            ),
            "recommended_fps": (
                recommended_fps
            ),
            "gps_clip_count": (
                gps_clip_count
            ),
        },
        "clips": report_clips,
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print("CLIP REPORT CREATED")
    print("=" * 60)

    print(
        f"Clips:      "
        f"{len(report_clips)}"
    )

    print(
        f"Resolution: "
        f"{recommended_width}x"
        f"{recommended_height}"
    )

    print(
        f"FPS:        "
        f"{recommended_fps}"
    )

    print(
        f"GPS:        "
        f"{gps_clip_count}/"
        f"{len(report_clips)} clips"
    )

    print()
    print("Written to:")
    print(REPORT_FILE)


if __name__ == "__main__":
    main()