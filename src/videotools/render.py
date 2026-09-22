"""FFmpeg rendering for JSON edit timelines."""

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from videotools.edit import EditTimeline, EditValidationError


class RenderError(RuntimeError):
    """Raised when media cannot be rendered."""


@dataclass(frozen=True)
class StreamSignature:
    video: tuple[tuple[str, Any], ...]
    audio: tuple[tuple[str, Any], ...] | None
    duration: float | None


_VIDEO_COMPATIBILITY_FIELDS = (
    "codec_name",
    "codec_tag_string",
    "profile",
    "width",
    "height",
    "pix_fmt",
    "level",
    "field_order",
    "avg_frame_rate",
    "time_base",
)

_AUDIO_COMPATIBILITY_FIELDS = (
    "codec_name",
    "codec_tag_string",
    "sample_fmt",
    "sample_rate",
    "channels",
    "channel_layout",
    "time_base",
)

_ACCURATE_VIDEO_FIELDS = (
    "width",
    "height",
    "pix_fmt",
)

_ACCURATE_AUDIO_FIELDS = (
    "sample_rate",
    "channels",
    "channel_layout",
)


def render_fast(
    timeline: EditTimeline,
    *,
    overwrite: bool = False,
) -> Path:
    """Render a timeline using a single FFmpeg stream-copy pass."""

    ffmpeg, signatures = _prepare_render(timeline, overwrite)
    _validate_stream_compatibility(signatures)

    concat_file: Path | None = None

    try:
        concat_file = _write_concat_file(timeline)
        command = build_fast_command(
            ffmpeg=ffmpeg,
            concat_file=concat_file,
            output=timeline.output,
            overwrite=overwrite,
        )

        _run_ffmpeg(command, timeline.output)
    finally:
        if concat_file is not None:
            concat_file.unlink(missing_ok=True)

    return timeline.output


def render_accurate(
    timeline: EditTimeline,
    *,
    overwrite: bool = False,
) -> Path:
    """Render exact requested cuts with one HEVC encoding pass."""

    ffmpeg, signatures = _prepare_render(timeline, overwrite)
    has_audio, pixel_format = _validate_accurate_compatibility(signatures)
    target_frame_rate = _accurate_target_frame_rate(timeline, signatures)

    command = build_accurate_command(
        ffmpeg=ffmpeg,
        timeline=timeline,
        has_audio=has_audio,
        pixel_format=pixel_format,
        target_frame_rate=target_frame_rate,
        overwrite=overwrite,
    )

    _run_ffmpeg(command, timeline.output)
    return timeline.output


def build_fast_command(
    *,
    ffmpeg: str,
    concat_file: Path,
    output: Path,
    overwrite: bool,
) -> list[str]:
    return [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-dn",
        "-c",
        "copy",
        "-y" if overwrite else "-n",
        str(output),
    ]


def build_accurate_command(
    *,
    ffmpeg: str,
    timeline: EditTimeline,
    has_audio: bool,
    pixel_format: str | None,
    target_frame_rate: str | None,
    overwrite: bool,
) -> list[str]:
    command = [
        ffmpeg,
        "-hide_banner",
        "-v",
        "error",
    ]

    for clip in timeline.clips:
        command.extend(
            (
                "-ss",
                f"{clip.start:.9f}",
                "-t",
                f"{clip.duration:.9f}",
                "-i",
                str(clip.file),
            )
        )

    command.extend(
        (
            "-filter_complex",
            build_accurate_filter(
                len(timeline.clips),
                has_audio,
                target_frame_rate=target_frame_rate,
            ),
            "-map",
            "[vout]",
        )
    )

    if has_audio:
        command.extend(("-map", "[aout]"))

    command.extend(
        (
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-sn",
            "-dn",
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-tag:v",
            "hvc1",
        )
    )

    if pixel_format:
        command.extend(("-pix_fmt", pixel_format))

    if has_audio:
        command.extend(("-c:a", "aac", "-b:a", "192k"))

    command.extend(
        (
            "-y" if overwrite else "-n",
            str(timeline.output),
        )
    )

    return command


def build_accurate_filter(
    clip_count: int,
    has_audio: bool,
    *,
    target_frame_rate: str | None = None,
) -> str:
    filters = []
    concat_inputs = []

    for index in range(clip_count):
        video_filters = []
        if target_frame_rate:
            video_filters.append(f"fps={target_frame_rate}")
        video_filters.append("setpts=PTS-STARTPTS")
        filters.append(
            f"[{index}:v:0]" + ",".join(video_filters) + f"[v{index}]"
        )
        concat_inputs.append(f"[v{index}]")

        if has_audio:
            filters.append(
                f"[{index}:a:0]asetpts=PTS-STARTPTS[a{index}]"
            )
            concat_inputs.append(f"[a{index}]")

    outputs = "[vout][aout]" if has_audio else "[vout]"
    filters.append(
        "".join(concat_inputs)
        + f"concat=n={clip_count}:v=1:a={1 if has_audio else 0}"
        + outputs
    )

    return ";".join(filters)


def build_concat_text(timeline: EditTimeline) -> str:
    lines = ["ffconcat version 1.0"]

    for clip in timeline.clips:
        lines.extend(
            (
                f"file '{_escape_concat_path(clip.file)}'",
                f"inpoint {clip.start:.9f}",
                f"outpoint {clip.end:.9f}",
            )
        )

    return "\n".join(lines) + "\n"


def probe_stream_signature(path: Path, ffprobe: str) -> StreamSignature:
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RenderError(f"Could not run ffprobe for {path}: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or "ffprobe returned an unknown error."
        raise RenderError(f"Could not inspect {path}:\n{detail}")

    try:
        info = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RenderError(f"ffprobe returned invalid JSON for {path}.") from error

    if not isinstance(info, dict):
        raise RenderError(f"ffprobe returned an invalid response for {path}.")

    video_stream = next(
        (
            stream
            for stream in info.get("streams", [])
            if stream.get("codec_type") == "video"
            and not (stream.get("disposition") or {}).get("attached_pic")
        ),
        None,
    )

    if video_stream is None:
        raise RenderError(f"No video stream found in {path}.")

    audio_stream = next(
        (
            stream
            for stream in info.get("streams", [])
            if stream.get("codec_type") == "audio"
        ),
        None,
    )

    duration = _parse_duration(info.get("format", {}).get("duration"))

    return StreamSignature(
        video=_field_values(video_stream, _VIDEO_COMPATIBILITY_FIELDS),
        audio=(
            _field_values(audio_stream, _AUDIO_COMPATIBILITY_FIELDS)
            if audio_stream is not None
            else None
        ),
        duration=duration,
    )


def _probe_timeline_sources(
    timeline: EditTimeline,
    ffprobe: str,
) -> dict[Path, StreamSignature]:
    signatures = {}

    for clip in timeline.clips:
        if clip.file not in signatures:
            signatures[clip.file] = probe_stream_signature(clip.file, ffprobe)

    return signatures


def _validate_clip_ranges(
    timeline: EditTimeline,
    signatures: dict[Path, StreamSignature],
) -> None:
    for index, clip in enumerate(timeline.clips):
        duration = signatures[clip.file].duration
        if duration is not None and clip.end > duration + 0.001:
            raise EditValidationError(
                f"clips[{index}].end ({clip.end:g}) exceeds the source "
                f"duration ({duration:g} seconds): {clip.file}"
            )


def _validate_stream_compatibility(
    signatures: dict[Path, StreamSignature],
) -> None:
    items = list(signatures.items())
    reference_path, reference = items[0]

    for path, signature in items[1:]:
        differences = []
        differences.extend(
            _signature_differences("video", reference.video, signature.video)
        )

        if reference.audio is None and signature.audio is not None:
            differences.append("audio presence")
        elif reference.audio is not None and signature.audio is None:
            differences.append("audio presence")
        elif reference.audio is not None and signature.audio is not None:
            differences.extend(
                _signature_differences("audio", reference.audio, signature.audio)
            )

        if differences:
            fields = ", ".join(differences)
            raise RenderError(
                "Fast mode requires compatible source streams. "
                f"{path} differs from {reference_path}: {fields}. "
                "Use accurate mode to re-encode sources with different codecs."
            )


def _validate_accurate_compatibility(
    signatures: dict[Path, StreamSignature],
) -> tuple[bool, str | None]:
    items = list(signatures.items())
    reference_path, reference = items[0]

    reference_video = dict(reference.video)
    reference_audio = dict(reference.audio) if reference.audio is not None else None

    for path, signature in items[1:]:
        video = dict(signature.video)
        differences = [
            f"video.{field}"
            for field in _ACCURATE_VIDEO_FIELDS
            if reference_video.get(field) != video.get(field)
        ]

        audio = dict(signature.audio) if signature.audio is not None else None

        if (reference_audio is None) != (audio is None):
            differences.append("audio presence")
        elif reference_audio is not None and audio is not None:
            differences.extend(
                f"audio.{field}"
                for field in _ACCURATE_AUDIO_FIELDS
                if reference_audio.get(field) != audio.get(field)
            )

        if differences:
            fields = ", ".join(differences)
            raise RenderError(
                "Accurate mode currently requires matching frame dimensions, "
                "pixel formats, and audio layouts. Frame-rate differences are "
                "normalized automatically. "
                f"{path} differs from {reference_path}: {fields}."
            )

    return reference_audio is not None, reference_video.get("pix_fmt")


def probe_timeline_sources(timeline: EditTimeline) -> dict[Path, StreamSignature]:
    """Probe and validate source files for a timeline without rendering it."""

    ffprobe = _find_executable("ffprobe")
    signatures = _probe_timeline_sources(timeline, ffprobe)
    _validate_clip_ranges(timeline, signatures)
    return signatures


def accurate_target_frame_rate(
    timeline: EditTimeline,
    signatures: dict[Path, StreamSignature],
) -> str | None:
    """Return the frame rate accurate mode will use for the rendered timeline."""

    return _accurate_target_frame_rate(timeline, signatures)


def _accurate_target_frame_rate(
    timeline: EditTimeline,
    signatures: dict[Path, StreamSignature],
) -> str | None:
    if not timeline.clips:
        return None
    return dict(signatures[timeline.clips[0].file].video).get("avg_frame_rate")


def validate_accurate_compatibility(
    signatures: dict[Path, StreamSignature],
) -> None:
    """Raise RenderError unless sources can share the accurate filter graph."""

    _validate_accurate_compatibility(signatures)

def _signature_differences(
    prefix: str,
    first: tuple[tuple[str, Any], ...],
    second: tuple[tuple[str, Any], ...],
) -> list[str]:
    first_values = dict(first)
    second_values = dict(second)

    return [
        f"{prefix}.{name}"
        for name in first_values
        if first_values[name] != second_values[name]
    ]


def _field_values(
    stream: dict,
    fields: tuple[str, ...],
) -> tuple[tuple[str, Any], ...]:
    return tuple((field, stream.get(field)) for field in fields)


def _parse_duration(value: Any) -> float | None:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        return None

    return duration if duration >= 0 else None


def _find_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RenderError(
            f"{name} was not found on PATH. Make sure FFmpeg is installed."
        )
    return executable


def _prepare_render(
    timeline: EditTimeline,
    overwrite: bool,
) -> tuple[str, dict[Path, StreamSignature]]:
    ffmpeg = _find_executable("ffmpeg")
    ffprobe = _find_executable("ffprobe")

    if timeline.output.exists() and not overwrite:
        raise RenderError(
            f"Output already exists: {timeline.output}. "
            "Use --overwrite to replace it."
        )

    signatures = _probe_timeline_sources(timeline, ffprobe)
    _validate_clip_ranges(timeline, signatures)
    timeline.output.parent.mkdir(parents=True, exist_ok=True)

    return ffmpeg, signatures


def _run_ffmpeg(command: list[str], output: Path) -> None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RenderError(f"Could not render {output}: {error}") from error

    if result.returncode != 0:
        if output.exists():
            output.unlink()

        detail = result.stderr.strip() or "FFmpeg returned an unknown error."
        raise RenderError(f"FFmpeg failed:\n{detail}")


def _write_concat_file(timeline: EditTimeline) -> Path:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".ffconcat",
        prefix="video-tools-",
        dir=timeline.output.parent,
        delete=False,
    ) as file:
        file.write(build_concat_text(timeline))
        return Path(file.name)


def _escape_concat_path(path: Path) -> str:
    # Forward slashes work in FFmpeg on Windows and avoid backslash escaping.
    return path.as_posix().replace("'", "'\\''")
