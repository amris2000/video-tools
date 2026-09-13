from dataclasses import dataclass
from pathlib import Path
import tomllib


def load_project_config(project_root: Path) -> dict:
    config_file = Path(project_root) / "project.toml"

    with config_file.open("rb") as file:
        return tomllib.load(file)


@dataclass(frozen=True)
class VideoProject:
    """Resolved paths and configuration for a video-tools project."""

    root: Path
    config: dict

    @classmethod
    def load(cls, root: Path) -> "VideoProject":
        resolved_root = Path(root).resolve()
        return cls(
            root=resolved_root,
            config=load_project_config(resolved_root),
        )

    def _configured_path(self, name: str, default: str) -> Path:
        configured = self.config.get("paths", {}).get(name, default)

        if not isinstance(configured, str) or not configured.strip():
            raise RuntimeError(
                f"project.toml paths.{name} must be a non-empty string."
            )

        path = (self.root / configured).resolve()

        if not path.is_relative_to(self.root):
            raise RuntimeError(
                f"project.toml paths.{name} must stay inside the project."
            )

        return path

    @property
    def name(self) -> str:
        configured = self.config.get("name")

        if isinstance(configured, str) and configured.strip():
            return configured.strip()

        return self.root.name

    @property
    def clips_dir(self) -> Path:
        return self._configured_path("clips", "clips")

    @property
    def metadata_dir(self) -> Path:
        return self._configured_path("metadata", "metadata")

    @property
    def exports_dir(self) -> Path:
        return self._configured_path("exports", "exports")

    @property
    def exports_social_dir(self) -> Path:
        return self._configured_path("exports_social", "exports-social")

    @property
    def edits_dir(self) -> Path:
        return self._configured_path("edits", "edits")

    @property
    def journal_file(self) -> Path:
        return self._configured_path("journal", "journal.json")


def find_project_root(start=None):
    current = Path(start or Path.cwd()).resolve()

    for path in [current, *current.parents]:
        if (path / "project.toml").exists():
            return path

    raise RuntimeError(
        "No video-tools project found. "
        "Expected project.toml in this directory or a parent directory."
    )
