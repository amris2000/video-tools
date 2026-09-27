from pathlib import Path
import tomllib

from fastapi import APIRouter, HTTPException

from videotools.config import load_config
from videotools.web.schemas import (
    ProjectPathsResponse,
    ProjectResponse,
)


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


@router.get("", response_model=list[ProjectResponse])
def get_projects() -> list[ProjectResponse]:
    config = load_config()

    if config.projects_directory is None:
        raise HTTPException(
            status_code=409,
            detail="Video Tools has not been configured.",
        )

    projects_directory = Path(
        config.projects_directory
    )

    if not projects_directory.exists():
        raise HTTPException(
            status_code=409,
            detail="Configured projects directory does not exist.",
        )

    projects: list[ProjectResponse] = []

    for directory in projects_directory.iterdir():
        if not directory.is_dir():
            continue

        project_file = directory / "project.toml"

        if not project_file.is_file():
            continue

        try:
            with project_file.open("rb") as file:
                project_config = tomllib.load(file)
        except (OSError, tomllib.TOMLDecodeError):
            continue

        project_name = project_config.get(
            "name",
            directory.name,
        )

        paths = project_config.get("paths", {})

        projects.append(
            ProjectResponse(
                id=directory.name,
                name=project_config.get(
                    "name",
                    directory.name,
                ),
                path=str(directory.resolve()),
                timezone=project_config.get("timezone"),
                paths=ProjectPathsResponse(
                    clips=paths.get("clips", "clips"),
                    metadata=paths.get("metadata", "metadata"),
                    exports=paths.get("exports", "exports"),
                    journal=paths.get("journal", "journal.json"),
                ),
            )
        )

    projects.sort(
        key=lambda project: project.name.lower()
    )

    return projects