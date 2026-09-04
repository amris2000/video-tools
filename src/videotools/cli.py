import argparse

from videotools.project import find_project_root


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
        "project",
        help="Show the current video project.",
    )

    subparsers.add_parser(
        "probe",
        help="Analyze clips in the current project.",
    )

    args = parser.parse_args()

    project_root = find_project_root()

    if args.command == "project":
        print(f"Project: {project_root}")

    elif args.command == "probe":
        print(f"Would analyze clips in: {project_root / 'clips'}")