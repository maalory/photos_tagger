from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import sys

APP_NAME = "PhotosTagger"


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    resource_root: Path
    user_data_dir: Path
    db_path: Path
    thumbnails_dir: Path
    logs_dir: Path
    tagy_path: Path


def get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_resource_root() -> Path:
    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            return Path(str(bundle_dir))
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_NAME
    return Path.home() / ".photos_tagger"


def get_tagy_path(project_root: Path, user_data_dir: Path) -> Path:
    project_tagy = project_root / "tagy.txt"
    if project_tagy.exists():
        return project_tagy

    if not getattr(sys, "frozen", False):
        return project_tagy

    if os.access(project_root, os.W_OK):
        return project_tagy
    return user_data_dir / "tagy.txt"


def build_app_paths() -> AppPaths:
    project_root = get_project_root()
    resource_root = get_resource_root()
    user_data_dir = get_user_data_dir()
    return AppPaths(
        project_root=project_root,
        resource_root=resource_root,
        user_data_dir=user_data_dir,
        db_path=user_data_dir / "catalog.sqlite3",
        thumbnails_dir=user_data_dir / "thumbnails",
        logs_dir=user_data_dir / "logs",
        tagy_path=get_tagy_path(project_root, user_data_dir),
    )


def ensure_app_paths(paths: AppPaths) -> None:
    paths.user_data_dir.mkdir(parents=True, exist_ok=True)
    paths.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    _ensure_external_tagy_file(paths)


def _ensure_external_tagy_file(paths: AppPaths) -> None:
    if paths.tagy_path.exists():
        return

    source_path = paths.resource_root / "tagy.txt"
    if not source_path.exists():
        return

    paths.tagy_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.resolve() == paths.tagy_path.resolve():
        return
    shutil.copyfile(source_path, paths.tagy_path)
