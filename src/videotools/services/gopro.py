from __future__ import annotations

import os
from pathlib import Path

from videotools.media import VIDEO_EXTENSIONS

_IGNORED_DIRECTORIES = {
    "$recycle.bin",
    "recycler",
    "system volume information",
    "lost+found",
}
_IGNORED_FILES = {"desktop.ini", "thumbs.db", "ehthumbs.db", ".ds_store"}
_HIDDEN_ATTRIBUTE = 0x2
_SYSTEM_ATTRIBUTE = 0x4


def discover_gopro_videos(source: Path) -> list[Path]:
    """Discover supported GoPro video files without following paths outside source."""

    root = Path(source).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"GoPro source directory does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"GoPro source is not a directory: {root}")

    videos: list[Path] = []
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories[:] = [
            name
            for name in directories
            if not _is_ignored(name)
            and _is_visible(current_path / name)
            and _is_within(current_path / name, root)
        ]
        for filename in filenames:
            path = current_path / filename
            if _is_ignored(filename) or not _is_visible(path):
                continue
            if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
                continue
            if _is_within(path, root):
                videos.append(path.resolve())

    return sorted(videos, key=lambda path: path.relative_to(root).as_posix().casefold())


def _is_ignored(name: str) -> bool:
    return name.startswith(".") or name.casefold() in (
        _IGNORED_DIRECTORIES | _IGNORED_FILES
    )


def _is_visible(path: Path) -> bool:
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return not attributes & (_HIDDEN_ATTRIBUTE | _SYSTEM_ATTRIBUTE)


def _is_within(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except OSError:
        return False
