from pathlib import Path


def find_project_root(start=None):
    current = Path(start or Path.cwd()).resolve()

    for path in [current, *current.parents]:
        if (path / "project.toml").exists():
            return path

    raise RuntimeError(
        "No video-tools project found. "
        "Expected project.toml in this directory or a parent directory."
    )