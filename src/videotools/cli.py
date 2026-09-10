import argparse

from videotools.init_project import create_project
from videotools.metadata import analyze_project
from videotools.project import find_project_root
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

    # project
    subparsers.add_parser(
        "project",
        help="Show the current video project.",
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

    # init does not need an existing project
    if args.command == "init":
        project_dir = create_project(args.name)

        print()
        print(f"Created video project: {args.name}")
        print(f"Location: {project_dir}")
        print()

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

    elif args.command == "journal":
        if args.journal_command == "add":
            add_journal_entry(project_root)

        elif args.journal_command == "list":
            list_journal_entries(project_root)