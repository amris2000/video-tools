from pathlib import Path

from fastapi import APIRouter, HTTPException

from videotools.config import AppConfig, load_config, save_config
from videotools.web.schemas import ConfigResponse, ConfigUpdate


router = APIRouter(
    prefix="/config",
    tags=["config"],
)


@router.get("", response_model=ConfigResponse)
def get_config() -> ConfigResponse:
    config = load_config()

    return ConfigResponse(
        configured=config.projects_directory is not None,
        projects_directory=config.projects_directory,
    )


@router.put("", response_model=ConfigResponse)
def update_config(update: ConfigUpdate) -> ConfigResponse:
    projects_directory = Path(update.projects_directory).expanduser()

    if not projects_directory.exists():
        raise HTTPException(
            status_code=400,
            detail="Projects directory does not exist.",
        )

    if not projects_directory.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Projects directory is not a directory.",
        )

    config = AppConfig(
        projects_directory=str(projects_directory.resolve()),
    )

    save_config(config)

    return ConfigResponse(
        configured=True,
        projects_directory=config.projects_directory,
    )