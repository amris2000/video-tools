import argparse
from pathlib import Path
import sys

import webbrowser
from importlib.resources import files

from videotools.edit import EditValidationError, load_edit_timeline
from videotools.init_project import create_project
from videotools.metadata import analyze_project
from videotools.project import VideoProject, find_project_root
from videotools.render import RenderError, render_accurate, render_fast
from videotools.sample_edit import (
    SampleEditError,
    create_sample_edit,
    create_selected_edit,
)
from videotools.journal import (
    add_journal_entry,
    list_journal_entries,
)

from videotools.organize import organize_clips
from videotools.thumbnails import (
    generate_project_thumbnails,
)



def main():
    parser = argparse.ArgumentParser(
        prog="video-tools",
        description="Tools for managing video projects.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "help",
        help="List all available commands.",
    )

    # project
    subparsers.add_parser(
        "project",
        help="Show the current video project.",
    )

    subparsers.add_parser(
        "editor",
        help="Open the video edit JSON editor in your browser.",
    )

    probe_parser = subparsers.add_parser(
        "probe",
        help="Analyze video clips in the current project.",
    )

    probe_parser.add_argument(
        "--force",
        action="store_true",
        help="Probe all clips again, ignoring cached metadata.",
    )

    subparsers.add_parser(
        "organize",
        help="Move loose clips into date folders.",
    )

    thumbnail_parser = subparsers.add_parser(
        "thumbnails",
        help="Generate thumbnails for video clips.",
    )

    thumbnail_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate thumbnails that already exist.",
    )

    render_parser = subparsers.add_parser(
        "render",
        help="Render a JSON edit timeline.",
    )

    render_parser.add_argument(
        "edit_file",
        type=Path,
        help="Path to the JSON edit file.",
    )

    render_parser.add_argument(
        "--mode",
        choices=("accurate", "fast"),
        default="accurate",
        help="Rendering strategy (default: accurate).",
    )

    render_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output file if it already exists.",
    )

    sample_edit_parser = subparsers.add_parser(
        "sample-edit",
        help="Create test-edit.json from existing project clips.",
    )

    sample_edit_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace test-edit.json if it already exists.",
    )

    select_edit_parser = subparsers.add_parser(
        "select-edit",
        help="Interactively select clips for selected-edit.json.",
    )

    select_edit_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace selected-edit.json if it already exists.",
    )

    journal_parser = subparsers.add_parser(
        "journal",
        help="Work with the current project's journal.",
    )

    journal_subparsers = journal_parser.add_subparsers(
        dest="journal_command",
        required=True,
    )

    journal_subparsers.add_parser(
        "add",
        help="Add a journal entry.",
    )

    journal_subparsers.add_parser(
        "list",
        help="List journal entries.",
    )

    # init
    init_parser = subparsers.add_parser(
        "init",
        help="Create a new video project.",
    )

    init_parser.add_argument(
        "name",
        help="Name of the new project.",
    )

    args = parser.parse_args()

    if args.command == "help":
        parser.print_help()
        print()
        print("Journal commands:")
        print("  video-tools journal add   Add a journal entry.")
        print("  video-tools journal list  List journal entries.")
        return

    # init does not need an existing project
    if args.command == "init":
        project_dir = create_project(args.name)

        print()
        print(f"Created video project: {args.name}")
        print(f"Location: {project_dir}")
        print()

        return

    if args.command == "editor":
        editor_file = files("videotools").joinpath(
            "editor",
            "index.html",
        )

        url = editor_file.as_uri()

        print(f"Opening editor: {url}")

        if not webbrowser.open(url):
            print(
                "Could not automatically open a browser.",
                file=sys.stderr,
            )
            print(f"Open this manually: {url}")

        return

    # All commands below this point require an existing project
    project_root = find_project_root()

    if args.command == "project":
        print(f"Project: {project_root}")

    elif args.command == "probe":
        analyze_project(
            project_root,
            force=args.force,
        )

    elif args.command == "thumbnails":
        generate_project_thumbnails(
            project_root,
            force=args.force,
        )

    elif args.command == "organize":
        organize_clips(project_root)

    elif args.command == "render":
        try:
            project = VideoProject.load(project_root)
            timeline = load_edit_timeline(
                args.edit_file,
                project,
            )
            print(f"Rendering ({args.mode})...")

            renderer = (
                render_fast
                if args.mode == "fast"
                else render_accurate
            )

            output = renderer(
                timeline,
                overwrite=args.overwrite,
            )
        except (EditValidationError, RenderError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        print(f"Rendered: {output}")

    elif args.command == "sample-edit":
        try:
            project = VideoProject.load(project_root)
            result = create_sample_edit(
                project,
                overwrite=args.overwrite,
            )
        except (SampleEditError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        print(f"Created: {result.edit_file}")
        print(f"Selected clips: {result.clip_count}")
        if result.skipped_count:
            print(f"Skipped clips: {result.skipped_count}")
        print("Render it with: video-tools render test-edit.json")

    elif args.command == "select-edit":
        try:
            project = VideoProject.load(project_root)
            result = create_selected_edit(
                project,
                overwrite=args.overwrite,
            )
        except (SampleEditError, OSError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            raise SystemExit(1) from error

        print(f"Created: {result.edit_file}")
        print(f"Selected clips: {result.clip_count}")
        if result.skipped_count:
            print(f"Unavailable clips: {result.skipped_count}")
        print("Render it with: video-tools render selected-edit.json")

    elif args.command == "journal":
        if args.journal_command == "add":
            add_journal_entry(project_root)

        elif args.journal_command == "list":
            list_journal_entries(project_root)
