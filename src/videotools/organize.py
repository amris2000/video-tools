from pathlib import Path
import shutil

from videotools.metadata import (
    VIDEO_EXTENSIONS,
    get_creation_time,
    load_project_config,
    parse_creation_time,
    probe_video,
)


def organize_clips(project_root: Path):
    project_root = Path(project_root).resolve()

    clips_dir = project_root / "clips"

    if not clips_dir.exists():
        raise RuntimeError(
            f"Clips directory does not exist: {clips_dir}"
        )

    config = load_project_config(project_root)

    timezone_name = config.get(
        "timezone",
        "Europe/Copenhagen",
    )

    # Important:
    # Only inspect files directly inside clips/.
    # Existing folders are left completely alone.
    clips = sorted(
        path
        for path in clips_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not clips:
        print()
        print("No loose video clips found.")
        print(f"Nothing to organize in: {clips_dir}")
        return

    print()
    print("=" * 60)
    print("ORGANIZING CLIPS")
    print("=" * 60)
    print()

    moved = 0
    skipped = 0
    failed = 0

    for index, clip in enumerate(clips, start=1):
        print(
            f"[{index}/{len(clips)}] "
            f"{clip.name}"
        )

        try:
            info = probe_video(clip)

            creation_time = get_creation_time(info)

            if not creation_time:
                print("  SKIP: no creation timestamp found")
                skipped += 1
                continue

            local_time = parse_creation_time(
                creation_time,
                timezone_name,
            )

            if local_time is None:
                print("  SKIP: could not parse creation timestamp")
                skipped += 1
                continue

            date_folder = local_time.strftime(
                "%Y%m%d"
            )

            destination_dir = (
                clips_dir / date_folder
            )

            destination = (
                destination_dir / clip.name
            )

            # Never overwrite an existing file.
            if destination.exists():
                print(
                    f"  SKIP: already exists in "
                    f"{date_folder}/"
                )
                skipped += 1
                continue

            destination_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(clip),
                str(destination),
            )

            print(
                f"  -> {date_folder}/{clip.name}"
            )

            moved += 1

        except Exception as error:
            print(
                f"  ERROR: {error}"
            )
            failed += 1

    print()
    print("=" * 60)
    print("ORGANIZE COMPLETE")
    print("=" * 60)
    print(f"Moved:   {moved}")
    print(f"Skipped: {skipped}")
    print(f"Failed:  {failed}")