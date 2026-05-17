from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

APP_NAME = "PhotosTagger"


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    user_data_dir: Path
    db_path: Path
    thumbnails_dir: Path
    logs_dir: Path


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / ".photos_tagger"


def build_app_paths() -> AppPaths:
    project_root = get_project_root()
    user_data_dir = get_user_data_dir()
    return AppPaths(
        project_root=project_root,
        user_data_dir=user_data_dir,
        db_path=user_data_dir / "catalog.sqlite3",
        thumbnails_dir=user_data_dir / "thumbnails",
        logs_dir=user_data_dir / "logs",
    )


def ensure_app_paths(paths: AppPaths) -> None:
    paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    paths.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
