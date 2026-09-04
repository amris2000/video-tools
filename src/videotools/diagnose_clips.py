from pathlib import Path
import subprocess
import json
from collections import Counter


PROJECT_DIR = Path(r"C:\Users\Frederik\Videos\Projects\dv-test")
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


def most_common(values):
    if not values:
        return None

    return Counter(values).most_common(1)[0][0]


def main():
    clips = sorted(
        path
        for path in CLIPS_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not clips:
        raise RuntimeError("No clips found.")

    report_clips = []

    for clip in clips:
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

        if video_stream is None:
            print(f"Skipping {clip.name}: no video stream")
            continue

        fps = parse_fps(
            video_stream.get("avg_frame_rate", "0/1")
        )

        duration = float(
            info.get("format", {}).get("duration", 0)
        )

        clip_info = {
            "name": clip.name,
            "path": str(clip),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
            "fps": round(fps, 3),
            "codec": video_stream.get("codec_name"),
            "pixel_format": video_stream.get("pix_fmt"),
            "duration": round(duration, 3),
            "audio": None,
        }

        if audio_stream:
            clip_info["audio"] = {
                "codec": audio_stream.get("codec_name"),
                "sample_rate": audio_stream.get("sample_rate"),
                "channels": audio_stream.get("channels"),
            }

        report_clips.append(clip_info)

    if not report_clips:
        raise RuntimeError("No usable video clips found.")

    widths = [clip["width"] for clip in report_clips]
    heights = [clip["height"] for clip in report_clips]
    fps_values = [clip["fps"] for clip in report_clips]

    recommended_width = most_common(widths)
    recommended_height = most_common(heights)
    recommended_fps = most_common(fps_values)

    report = {
        "summary": {
            "clip_count": len(report_clips),
            "recommended_width": recommended_width,
            "recommended_height": recommended_height,
            "recommended_fps": recommended_fps,
        },
        "clips": report_clips,
    }

    REPORT_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("CLIP REPORT CREATED")
    print("=" * 60)
    print(f"Clips:      {len(report_clips)}")
    print(
        f"Resolution: {recommended_width}x{recommended_height}"
    )
    print(f"FPS:        {recommended_fps}")
    print()
    print(f"Written to:")
    print(REPORT_FILE)


if __name__ == "__main__":
    main()