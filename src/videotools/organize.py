"""CLI wrapper around the reusable clip-organization service."""

from pathlib import Path

from videotools.project import VideoProject
from videotools.services.organize import (
    list_loose_clips,
    organize_project_clips,
)


def organize_clips(project_root: Path):
    project_root = Path(project_root).resolve()

    project = VideoProject.load(project_root)

    # Important:
    # Only inspect files directly inside clips/.
    # Existing folders are left completely alone.
    clips = list_loose_clips(project)

    if not clips:
        print()
        print("No loose video clips found.")
        print(f"Nothing to organize in: {project.clips_dir}")
        return

    print()
    print("=" * 60)
    print("ORGANIZING CLIPS")
    print("=" * 60)
    print()

    def print_event(event: dict) -> None:
        if event["status"] == "running":
            print(
                f"[{event['completed'] + 1}/{event['total']}] "
                f"{event['current_file']}"
            )
            return

        outcome = event.get("outcome")
        if outcome == "moved":
            print(f"  -> {event['detail']}")
        elif outcome == "skipped":
            print(f"  SKIP: {event['detail']}")
        else:
            print(f"  ERROR: {event['detail']}")

    result = organize_project_clips(
        project,
        clips,
        progress_callback=print_event,
    )

    print()
    print("=" * 60)
    print("ORGANIZE COMPLETE")
    print("=" * 60)
    print(f"Moved:   {result['moved']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Failed:  {result['failed']}")
