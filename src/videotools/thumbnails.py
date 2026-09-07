from pathlib import Path
import hashlib
import shutil
import subprocess

from videotools.media import VIDEO_EXTENSIONS


def thumbnail_name(
    clip: Path,
    project_root: Path,
) -> str:
    relative_path = clip.relative_to(
        project_root
    ).as_posix()

    digest = hashlib.sha1(
        relative_path.encode("utf-8")
    ).hexdigest()[:10]

    return f"{clip.stem}-{digest}.webp"


def generate_thumbnail(
    clip: Path,
    output_file: Path,
):
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg was not found on PATH."
        )

    command = [
        ffmpeg,
        "-v",
        "error",

        # Seek a little into the clip so we don't
        # constantly get the very first frame.
        "-ss",
        "1",

        "-i",
        str(clip),

        # Only one frame.
        "-frames:v",
        "1",

        # Keep aspect ratio, max width 480px.
        "-vf",
        "scale=480:-2",

        "-y",
        str(output_file),
    ]

    subprocess.run(
        command,
        check=True,
    )


def generate_project_thumbnails(
    project_root: Path,
    force: bool = False,
):
    project_root = Path(
        project_root
    ).resolve()

    clips_dir = project_root / "clips"

    thumbnails_dir = (
        project_root
        / "metadata"
        / "thumbnails"
    )

    if not clips_dir.exists():
        raise RuntimeError(
            f"Clips directory does not exist: {clips_dir}"
        )

    thumbnails_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    clips = sorted(
        path
        for path in clips_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in VIDEO_EXTENSIONS
    )

    if not clips:
        print()
        print("No video clips found.")
        return

    print()
    print("=" * 60)
    print("GENERATING THUMBNAILS")
    print("=" * 60)
    print()

    generated = 0
    skipped = 0
    failed = 0

    for index, clip in enumerate(
        clips,
        start=1,
    ):
        name = thumbnail_name(
            clip,
            project_root,
        )

        output_file = (
            thumbnails_dir / name
        )

        print(
            f"[{index}/{len(clips)}] "
            f"{clip.name}"
        )

        if (
            output_file.exists()
            and not force
        ):
            print("  SKIP: thumbnail already exists")
            skipped += 1
            continue

        try:
            generate_thumbnail(
                clip,
                output_file,
            )

            print(
                f"  -> metadata/thumbnails/{name}"
            )

            generated += 1

        except subprocess.CalledProcessError:
            print("  ERROR: ffmpeg failed")
            failed += 1

    print()
    print("=" * 60)
    print("THUMBNAILS COMPLETE")
    print("=" * 60)
    print(f"Generated: {generated}")
    print(f"Skipped:   {skipped}")
    print(f"Failed:    {failed}")