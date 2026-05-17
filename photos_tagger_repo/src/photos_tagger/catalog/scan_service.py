from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os

from photos_tagger.domain import MediaType

PHOTO_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
    ".heif",
    ".avif",
    ".raw",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".orf",
    ".rw2",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".mts",
    ".m2ts",
    ".wmv",
    ".webm",
}


@dataclass(frozen=True, slots=True)
class ScannedFolder:
    relative_path: str
    absolute_path: str
    folder_name: str
    parent_relative_path: str | None


@dataclass(frozen=True, slots=True)
class ScannedAsset:
    folder_relative_path: str
    relative_path: str
    absolute_path: str
    file_name: str
    extension: str | None
    media_type: MediaType
    file_size: int
    modified_at_fs: str


@dataclass(frozen=True, slots=True)
class ScanResult:
    source_root: str
    scanned_at: str
    folders: list[ScannedFolder]
    assets: list[ScannedAsset]


class DirectoryScanner:
    def scan_source(self, root_path: str) -> ScanResult:
        root = Path(root_path).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Zdrojová složka neexistuje nebo není adresář: {root_path}")

        folders: list[ScannedFolder] = []
        assets: list[ScannedAsset] = []

        for current_dir, subdirs, filenames in os.walk(root):
            subdirs.sort(key=str.lower)
            filenames.sort(key=str.lower)

            current_path = Path(current_dir)
            relative_dir = _to_relative_dir(root, current_path)
            parent_relative = _parent_relative_path(relative_dir)
            folder_name = root.name if relative_dir == "" else current_path.name
            folders.append(
                ScannedFolder(
                    relative_path=relative_dir,
                    absolute_path=str(current_path.resolve()),
                    folder_name=folder_name,
                    parent_relative_path=parent_relative,
                )
            )

            for file_name in filenames:
                file_path = current_path / file_name
                media_type = _detect_media_type(file_path)
                if media_type is None:
                    continue

                try:
                    stat = file_path.stat()
                except OSError:
                    continue

                assets.append(
                    ScannedAsset(
                        folder_relative_path=relative_dir,
                        relative_path=_to_posix(file_path.relative_to(root)),
                        absolute_path=str(file_path.resolve()),
                        file_name=file_path.name,
                        extension=file_path.suffix.lower() or None,
                        media_type=media_type,
                        file_size=int(stat.st_size),
                        modified_at_fs=_timestamp_to_iso(stat.st_mtime),
                    )
                )

        return ScanResult(
            source_root=str(root),
            scanned_at=_now_iso(),
            folders=folders,
            assets=assets,
        )



def _detect_media_type(path: Path) -> MediaType | None:
    extension = path.suffix.lower()
    if extension in PHOTO_EXTENSIONS:
        return MediaType.PHOTO
    if extension in VIDEO_EXTENSIONS:
        return MediaType.VIDEO
    return None



def _to_relative_dir(root: Path, current_path: Path) -> str:
    if current_path == root:
        return ""
    return _to_posix(current_path.relative_to(root))



def _parent_relative_path(relative_dir: str) -> str | None:
    if relative_dir == "":
        return None
    parent = Path(relative_dir).parent
    if str(parent) == ".":
        return ""
    return _to_posix(parent)



def _to_posix(path: Path) -> str:
    return path.as_posix()



def _timestamp_to_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")



def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
