from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Callable

from videotools.edit import EditValidationError, load_edit_timeline, parse_edit_timeline
from videotools.edit_files import create_render_output_path, list_edit_files, read_edit_document
from videotools.project import VideoProject
from videotools.render import (
    accurate_target_frame_rate,
    probe_timeline_sources,
    render_accurate,
    render_fast,
    validate_accurate_compatibility,
)


def choose_render_mode(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> str | None:
    output_func("Render mode:")
    output_func("")
    output_func("  1. Accurate")
    output_func("     Exact cuts with re-encoding. Recommended for normal use.")
    output_func("")
    output_func("  2. Fast")
    output_func("     Stream-copy rendering. Faster, but requires compatible source streams.")
    output_func("")

    while True:
        value = input_func("Choose mode [1]: ").strip().lower()

        if value in {"", "1", "accurate", "a"}:
            return "accurate"
        if value in {"2", "fast", "f"}:
            return "fast"
        if value in {"q", "quit"}:
            output_func("Render cancelled.")
            return None

        output_func("Please choose 1 or 2.")
        output_func("")


def choose_edit_file(
    edit_files: list[Path],
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> Path | None:
    output_func("Available edits:")
    output_func("")

    for index, edit_file in enumerate(edit_files, start=1):
        output_func(f"  {index}. {edit_file.name}{_edit_clip_count_hint(edit_file)}")

    output_func("")

    while True:
        value = input_func("Choose edit: ").strip().lower()

        if value in {"q", "quit"}:
            output_func("Render cancelled.")
            return None

        try:
            index = int(value)
        except ValueError:
            output_func("Please enter an edit number or q to cancel.")
            output_func("")
            continue

        if index < 1 or index > len(edit_files):
            output_func(f"Choose a number from 1 to {len(edit_files)}.")
            output_func("")
            continue

        return edit_files[index - 1]


def _edit_clip_count_hint(edit_file: Path) -> str:
    try:
        document = read_edit_document(edit_file)
    except (OSError, ValueError):
        return ""

    clips = document.get("clips")
    if not isinstance(clips, list):
        return ""

    count = len(clips)
    return f" ({count} clip{'s' if count != 1 else ''})"


def print_no_edits_message(
    project: VideoProject,
    *,
    output_func: Callable[[str], None] = print,
) -> None:
    output_func("No edit files found in:")
    output_func(f"  {project.edits_dir}")
    output_func("")
    output_func("Create one with:")
    output_func("")
    output_func("  video-tools editor")
    output_func("  video-tools sample-edit")
    output_func("  video-tools select-edit")


def print_render_summary(
    *,
    project: VideoProject,
    edit_file: Path,
    mode: str,
    clip_count: int,
    output_path: Path,
    output_func: Callable[[str], None] = print,
) -> None:
    output_func("Rendering:")
    output_func("")
    output_func(f"  Edit: {edit_file.relative_to(project.root).as_posix()}")
    output_func(f"  Mode: {mode}")
    output_func(f"  Clips: {clip_count}")
    output_func(f"  Output: {output_path.relative_to(project.root).as_posix()}")
    output_func("")


def _format_frame_rate(value: object) -> str:
    if not value or value == "0/0":
        return "unknown"
    try:
        return f"{float(Fraction(str(value))):.3f} fps"
    except (ValueError, ZeroDivisionError):
        return str(value)


def _format_duration(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    minutes, remainder = divmod(total_ms, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def print_render_preflight(
    *,
    timeline,
    mode: str,
    signatures,
    output_func: Callable[[str], None] = print,
) -> None:
    total_duration = sum(clip.duration for clip in timeline.clips)
    frame_rate_groups: dict[str, list[str]] = {}

    for path, signature in signatures.items():
        rate = dict(signature.video).get("avg_frame_rate")
        frame_rate_groups.setdefault(str(rate), []).append(path.name)

    output_func("Preflight:")
    output_func("")
    output_func(f"  Timeline duration: {_format_duration(total_duration)}")
    output_func(f"  Source files: {len(signatures)}")
    output_func("  Frame rates:")
    for rate, files in frame_rate_groups.items():
        output_func(f"    {_format_frame_rate(rate)}: {len(files)} file{'s' if len(files) != 1 else ''}")

    if len(frame_rate_groups) > 1:
        output_func("")
        output_func("  Frame-rate differences detected:")
        for rate, files in frame_rate_groups.items():
            output_func(f"    {_format_frame_rate(rate)}: {', '.join(files)}")

        if mode == "accurate":
            target = accurate_target_frame_rate(timeline, signatures)
            output_func(f"  Accurate mode will normalize video to {_format_frame_rate(target)}.")
        else:
            output_func("  Fast mode may reject these sources because it does not re-encode them.")

    output_func("")


def confirm_render(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> bool:
    while True:
        value = input_func("Render? [Y/n]: ").strip().lower()
        if value in {"", "y", "yes"}:
            return True
        if value in {"n", "no", "q", "quit"}:
            output_func("Render cancelled.")
            return False
        output_func("Please enter y or n.")


def run_render_workflow(
    project: VideoProject,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> Path | None:
    mode = choose_render_mode(
        input_func=input_func,
        output_func=output_func,
    )
    if mode is None:
        return None

    edit_files = list_edit_files(project)
    if not edit_files:
        print_no_edits_message(project, output_func=output_func)
        return None

    output_func("")
    edit_file = choose_edit_file(
        edit_files,
        input_func=input_func,
        output_func=output_func,
    )
    if edit_file is None:
        return None

    fallback_output_path: Path | None = None
    try:
        timeline = load_edit_timeline(edit_file, project)
    except EditValidationError as error:
        if "output must be a non-empty string." not in str(error):
            raise

        # Support legacy edit files that omitted "output" by assigning a
        # fresh timestamped filename for this render run.
        raw_document = read_edit_document(edit_file)
        fallback_output_path = create_render_output_path(project, mode)
        raw_document["output"] = fallback_output_path.relative_to(project.exports_dir).as_posix()
        timeline = parse_edit_timeline(raw_document, project)

    # Every render gets a fresh output. The edit document's output field is
    # descriptive only for this interactive workflow.
    output_path = create_render_output_path(project, mode)
    render_timeline = replace(timeline, output=output_path)

    signatures = probe_timeline_sources(render_timeline)
    if mode == "accurate":
        validate_accurate_compatibility(signatures)

    print_render_summary(
        project=project,
        edit_file=edit_file,
        mode=mode,
        clip_count=len(render_timeline.clips),
        output_path=output_path,
        output_func=output_func,
    )
    print_render_preflight(
        timeline=render_timeline,
        mode=mode,
        signatures=signatures,
        output_func=output_func,
    )

    if not confirm_render(input_func=input_func, output_func=output_func):
        return None

    output_func("Rendering...")

    renderer = render_fast if mode == "fast" else render_accurate
    output = renderer(render_timeline, overwrite=False)

    output_func("")
    output_func("Rendered:")
    output_func(f"  {output.relative_to(project.root).as_posix()}")
    return output