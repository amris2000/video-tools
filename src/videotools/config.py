from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from platformdirs import user_config_dir


APP_NAME = "video-tools"


@dataclass
class AppConfig:
    projects_directory: str | None = None


def get_config_directory() -> Path:
    return Path(user_config_dir(APP_NAME))


def get_config_path() -> Path:
    return get_config_directory() / "config.json"


def load_config() -> AppConfig:
    path = get_config_path()

    if not path.exists():
        return AppConfig()

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return AppConfig(
        projects_directory=data.get("projects_directory"),
    )


def save_config(config: AppConfig) -> None:
    directory = get_config_directory()
    directory.mkdir(parents=True, exist_ok=True)

    path = get_config_path()

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            asdict(config),
            file,
            indent=2,
        )