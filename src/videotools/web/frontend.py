from __future__ import annotations

from pathlib import Path


def find_frontend_build() -> Path | None:
    """
    Locate the built React frontend.

    Returns None when the frontend has not been built yet.
    """
    current = Path(__file__).resolve()

    for parent in current.parents:
        candidate = parent / "build" / "frontend"

        if (candidate / "index.html").is_file():
            return candidate

    return None