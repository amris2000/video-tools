from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_repository_root() -> Path:
    """
    Locate the repository root when Video Tools is installed
    in editable/development mode.
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (
            (parent / "pyproject.toml").is_file()
            and (parent / "frontend").is_dir()
        ):
            return parent

    raise RuntimeError(
        "Could not locate the Video Tools repository root."
    )


def require_command(command: str) -> str:
    path = shutil.which(command)

    if path is None:
        raise RuntimeError(
            f"Required command '{command}' was not found on PATH."
        )

    return path


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
) -> None:
    print(f"> {' '.join(command)}")

    subprocess.run(
        command,
        cwd=cwd,
        check=True,
    )


def install() -> None:
    root = find_repository_root()
    frontend = root / "frontend"

    print("Installing Amris Video Tools")
    print()

    print(f"Python: {sys.executable}")

    ffmpeg = require_command("ffmpeg")
    ffprobe = require_command("ffprobe")
    node = require_command("node")
    npm = require_command("npm")

    print(f"FFmpeg: {ffmpeg}")
    print(f"FFprobe: {ffprobe}")
    print(f"Node: {node}")
    print(f"npm: {npm}")
    print()

    print("Installing frontend dependencies...")
    run_command(
        [npm, "install"],
        cwd=frontend,
    )

    print()
    print("Building React frontend...")
    run_command(
        [npm, "run", "build"],
        cwd=frontend,
    )

    build_directory = root / "build" / "frontend"

    if not (build_directory / "index.html").is_file():
        raise RuntimeError(
            "Frontend build completed but "
            "build/frontend/index.html was not found."
        )

    print()
    print("Video Tools installation is ready.")
    print(f"Frontend build: {build_directory}")


def update() -> None:
    root = find_repository_root()
    frontend = root / "frontend"

    npm = require_command("npm")

    print("Updating Amris Video Tools")
    print()

    print("Installing current frontend dependencies...")
    run_command(
        [npm, "install"],
        cwd=frontend,
    )

    print()
    print("Rebuilding React frontend...")
    run_command(
        [npm, "run", "build"],
        cwd=frontend,
    )

    print()
    print("Video Tools update complete.")