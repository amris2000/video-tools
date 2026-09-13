from __future__ import annotations

from pathlib import Path
from typing import Callable

from videotools.edit_files import list_render_files
from videotools.project import VideoProject
from videotools.social import (
    FramingMode,
    SOCIAL_PRESETS,
    SocialPreset,
    convert_social_video,
    create_social_output_path,
)


def choose_source_render(
    render_files: list[Path],
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> Path | None:
    output_func("Available renders:")
    output_func("")

    for index, render_file in enumerate(render_files, start=1):
        output_func(f"  {index}. {render_file.name}")

    output_func("")

    while True:
        value = input_func("Choose render: ").strip().lower()

        if value in {"q", "quit"}:
            output_func("Social export cancelled.")
            return None

        try:
            index = int(value)
        except ValueError:
            output_func("Please enter a render number or q to cancel.")
            output_func("")
            continue

        if index < 1 or index > len(render_files):
            output_func(f"Choose a number from 1 to {len(render_files)}.")
            output_func("")
            continue

        return render_files[index - 1]


def choose_social_preset(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> SocialPreset | None:
    output_func("Social format:")
    output_func("")

    for index, preset in enumerate(SOCIAL_PRESETS, start=1):
        output_func(f"  {index}. {preset.name}")
        output_func(f"     {preset.description}")
        output_func("")

    while True:
        value = input_func("Choose format [1]: ").strip().lower()

        if value in {"q", "quit"}:
            output_func("Social export cancelled.")
            return None
        if value in {"", "1"}:
            return SOCIAL_PRESETS[0]

        output_func("Please choose 1 or q to cancel.")
        output_func("")


def choose_framing(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> FramingMode | None:
    output_func("Framing:")
    output_func("")
    output_func("  1. Crop to fill")
    output_func("     Fill the full 9:16 frame. Parts of the left/right image may be removed.")
    output_func("")
    output_func("  2. Fit with padding")
    output_func("     Keep the whole image visible and add padding where necessary.")
    output_func("")

    while True:
        value = input_func("Choose framing [1]: ").strip().lower()

        if value in {"q", "quit"}:
            output_func("Social export cancelled.")
            return None
        if value in {"", "1", "crop"}:
            return "crop"
        if value in {"2", "fit"}:
            return "fit"

        output_func("Please choose 1, 2, or q to cancel.")
        output_func("")


def print_no_renders_message(
    *,
    output_func: Callable[[str], None] = print,
) -> None:
    output_func("No rendered videos found.")
    output_func("")
    output_func("Create one first with:")
    output_func("")
    output_func("  video-tools render")


def print_social_summary(
    *,
    project: VideoProject,
    source: Path,
    preset: SocialPreset,
    framing: FramingMode,
    output_path: Path,
    output_func: Callable[[str], None] = print,
) -> None:
    framing_name = "Crop to fill" if framing == "crop" else "Fit with padding"

    output_func("Social export:")
    output_func("")
    output_func(f"  Source:   {source.relative_to(project.root).as_posix()}")
    output_func(f"  Format:   {preset.name}")
    output_func(f"  Framing:  {framing_name}")
    output_func(f"  Size:     {preset.width}x{preset.height}")
    output_func("  Video:    H.264")
    output_func("  Audio:    AAC")
    output_func(f"  Output:   {output_path.relative_to(project.root).as_posix()}")
    output_func("")


def run_social_workflow(
    project: VideoProject,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> Path | None:
    render_files = list_render_files(project)
    if not render_files:
        print_no_renders_message(output_func=output_func)
        return None

    source = choose_source_render(
        render_files,
        input_func=input_func,
        output_func=output_func,
    )
    if source is None:
        return None

    output_func("")
    preset = choose_social_preset(
        input_func=input_func,
        output_func=output_func,
    )
    if preset is None:
        return None

    framing = choose_framing(
        input_func=input_func,
        output_func=output_func,
    )
    if framing is None:
        return None

    output_path = create_social_output_path(project, source, preset)

    print_social_summary(
        project=project,
        source=source,
        preset=preset,
        framing=framing,
        output_path=output_path,
        output_func=output_func,
    )
    output_func("Converting...")

    converted = convert_social_video(
        source=source,
        output=output_path,
        preset=preset,
        framing=framing,
    )

    output_func("")
    output_func("Created:")
    output_func(f"  {converted.relative_to(project.root).as_posix()}")
    return converted
