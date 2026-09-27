from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def find_repository_root() -> Path:
    """
    Locate the Video Tools repository root.

    Lifecycle commands are intended for an editable/development
    installation where the frontend source is available.
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (
            (parent / "pyproject.toml").is_file()
            and (parent / "frontend").is_dir()
        ):
            return parent

    raise RuntimeError(
        "Could not locate the Video Tools repository root. "
        "Lifecycle commands require a source checkout."
    )


def require_command(command: str) -> str:
    executable = shutil.which(command)

    if executable is None:
        raise RuntimeError(
            f"Required command '{command}' was not found on PATH."
        )

    return executable


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


def verify_frontend_build(
    root: Path,
) -> Path:
    build_directory = root / "build" / "frontend"
    index_file = build_directory / "index.html"

    if not index_file.is_file():
        raise RuntimeError(
            "Frontend build completed, but "
            "build/frontend/index.html was not found."
        )

    return build_directory


def install() -> None:
    root = find_repository_root()
    frontend = root / "frontend"

    print("Installing Amris Video Tools")
    print()

    print(f"Repository: {root}")
    print(f"Python:     {sys.executable}")

    ffmpeg = require_command("ffmpeg")
    ffprobe = require_command("ffprobe")
    node = require_command("node")
    npm = require_command("npm")

    print(f"FFmpeg:     {ffmpeg}")
    print(f"FFprobe:    {ffprobe}")
    print(f"Node:       {node}")
    print(f"npm:        {npm}")
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

    build_directory = verify_frontend_build(
        root
    )

    print()
    print("Amris Video Tools is ready.")
    print(f"Frontend build: {build_directory}")


def update() -> None:
    root = find_repository_root()
    frontend = root / "frontend"

    npm = require_command("npm")

    print("Updating Amris Video Tools")
    print()

    print("Refreshing frontend dependencies...")
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

    build_directory = verify_frontend_build(
        root
    )

    print()
    print("Amris Video Tools update complete.")
    print(f"Frontend build: {build_directory}")


def dev() -> None:
    root = find_repository_root()
    frontend = root / "frontend"

    npm = require_command("npm")

    print(
        "Starting Amris Video Tools "
        "development environment"
    )
    print()
    print("FastAPI: http://127.0.0.1:8765")
    print("React:   http://localhost:5173")
    print()
    print("Press Ctrl+C to stop.")
    print()

    backend = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "videotools.web.app:app",
            "--reload",
            "--port",
            "8765",
        ],
        cwd=root,
    )

    try:
        frontend_process = subprocess.Popen(
            [
                npm,
                "run",
                "dev",
            ],
            cwd=frontend,
        )
    except Exception:
        backend.terminate()
        backend.wait()
        raise

    try:
        # Wait until either process exits.
        while True:
            backend_status = backend.poll()
            frontend_status = (
                frontend_process.poll()
            )

            if backend_status is not None:
                break

            if frontend_status is not None:
                break

            try:
                backend.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                pass

    except KeyboardInterrupt:
        print()
        print("Stopping development servers...")

    finally:
        for process in (
            frontend_process,
            backend,
        ):
            if process.poll() is None:
                process.terminate()

        for process in (
            frontend_process,
            backend,
        ):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()