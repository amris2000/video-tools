"""Create a small, ready-to-render edit from project footage."""

from dataclasses import dataclass
from collections.abc import Callable
import json
from pathlib import Path
import shutil

from videotools.media import VIDEO_EXTENSIONS
from videotools.project import VideoProject
from videotools.render import (
    RenderError,
    StreamSignature,
    probe_stream_signature,
    validate_accurate_compatibility,
)


class SampleEditError(RuntimeError):
    """Raised when a sample edit cannot be created."""


@dataclass(frozen=True)
class SampleEditResult:
    edit_file: Path
    clip_count: int
    skipped_count: int


@dataclass(frozen=True)
class ProbedClip:
    path: Path
    signature: StreamSignature


def create_sample_edit(
    project: VideoProject,
    *,
    overwrite: bool = False,
    max_clips: int = 3,
    selection_seconds: float = 3.0,
) -> SampleEditResult:
    """Create test-edit.json from a compatible group of project clips."""

    edit_file = project.root / "test-edit.json"

    if edit_file.exists() and not overwrite:
        raise SampleEditError(
            f"Sample edit already exists: {edit_file}. "
            "Use --overwrite to replace it."
        )

    if max_clips < 1:
        raise ValueError("max_clips must be at least 1.")
    if selection_seconds <= 0:
        raise ValueError("selection_seconds must be greater than zero.")

    clips, total_clip_count = _probe_project_clips(project)

    groups: dict[
        tuple[tuple[tuple[str, object], ...], tuple[tuple[str, object], ...] | None],
        list[ProbedClip],
    ] = {}

    for clip in clips:
        # Exact stream signatures form a conservative group that works with
        # both accurate rendering and fast stream-copy rendering.
        key = (clip.signature.video, clip.signature.audio)
        groups.setdefault(key, []).append(clip)

    compatible_clips = max(groups.values(), key=len)[:max_clips]
    selections = [
        _selection(
            project,
            clip.path,
            clip.signature.duration,
            selection_seconds,
        )
        for clip in compatible_clips
    ]

    document = {
        "version": 1,
        "output": "test-video.mp4",
        "clips": selections,
    }

    _write_edit_file(edit_file, document)

    return SampleEditResult(
        edit_file=edit_file,
        clip_count=len(selections),
        skipped_count=total_clip_count - len(compatible_clips),
    )


def create_selected_edit(
    project: VideoProject,
    *,
    overwrite: bool = False,
    selection_seconds: float = 3.0,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> SampleEditResult:
    """Interactively choose clips in timeline order."""

    edit_file = project.root / "selected-edit.json"

    if edit_file.exists() and not overwrite:
        raise SampleEditError(
            f"Selected edit already exists: {edit_file}. "
            "Use --overwrite to replace it."
        )

    if selection_seconds <= 0:
        raise ValueError("selection_seconds must be greater than zero.")

    clips, total_clip_count = _probe_project_clips(project)

    output_func("")
    output_func("Available clips:")
    for index, clip in enumerate(clips, start=1):
        relative = clip.path.relative_to(project.clips_dir).as_posix()
        output_func(
            f"  {index:>3}. {relative} "
            f"({clip.signature.duration:.1f} seconds)"
        )

    output_func("")
    output_func("Enter clip numbers in the order they should appear.")
    output_func("Enter q, quit, or done when finished.")

    selected: list[ProbedClip] = []

    while True:
        value = input_func("Clip number: ").strip().lower()

        if value in {"q", "quit", "done"}:
            break

        try:
            index = int(value)
        except ValueError:
            output_func("Please enter a clip number or q to finish.")
            continue

        if index < 1 or index > len(clips):
            output_func(f"Choose a number from 1 to {len(clips)}.")
            continue

        candidate = clips[index - 1]

        if selected:
            try:
                validate_accurate_compatibility(
                    {
                        selected[0].path: selected[0].signature,
                        candidate.path: candidate.signature,
                    }
                )
            except RenderError as error:
                output_func(f"Cannot add that clip: {error}")
                continue

        selected.append(candidate)
        output_func(
            f"Added {candidate.path.name} "
            f"as clip {len(selected)}."
        )

    if not selected:
        raise SampleEditError("No clips selected; no edit file was created.")

    document = {
        "version": 1,
        "output": "selected-video.mp4",
        "clips": [
            _selection(
                project,
                clip.path,
                clip.signature.duration,
                selection_seconds,
            )
            for clip in selected
        ],
    }

    _write_edit_file(edit_file, document)

    return SampleEditResult(
        edit_file=edit_file,
        clip_count=len(selected),
        skipped_count=total_clip_count - len(clips),
    )


def _probe_project_clips(
    project: VideoProject,
) -> tuple[list[ProbedClip], int]:
    paths = sorted(
        path
        for path in project.clips_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not paths:
        raise SampleEditError(
            f"No video clips found in {project.clips_dir}."
        )

    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise SampleEditError(
            "ffprobe was not found on PATH. Make sure FFmpeg is installed."
        )

    clips = []

    for path in paths:
        try:
            signature = probe_stream_signature(path, ffprobe)
        except RenderError:
            continue

        if signature.duration is None or signature.duration < 0.1:
            continue

        clips.append(ProbedClip(path=path, signature=signature))

    if not clips:
        raise SampleEditError(
            "No usable video clips with readable durations were found."
        )

    return clips, len(paths)


def _write_edit_file(edit_file: Path, document: dict) -> None:
    try:
        edit_file.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        raise SampleEditError(
            f"Could not write edit file {edit_file}: {error}"
        ) from error


def _selection(
    project: VideoProject,
    clip: Path,
    duration: float | None,
    selection_seconds: float,
) -> dict:
    if duration is None:
        raise ValueError("A sample selection requires a known duration.")

    selected_duration = min(selection_seconds, duration)
    start = max(0.0, (duration - selected_duration) / 2)
    end = min(duration, start + selected_duration)

    return {
        "file": clip.relative_to(project.clips_dir).as_posix(),
        "start": round(start, 3),
        "end": round(end, 3),
        "label": f"Sample from {clip.name}",
    }
