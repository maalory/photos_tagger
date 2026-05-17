from __future__ import annotations

from enum import Enum


class MediaType(str, Enum):
    PHOTO = "photo"
    VIDEO = "video"


class GroupingMode(str, Enum):
    AUTO = "auto"
    MANUAL = "manual"


class AlbumType(str, Enum):
    STATIC = "static"
    SMART = "smart"
    EVENT = "event"


class TagScope(str, Enum):
    ASSET = "asset"
    FOLDER = "folder"
    EVENT = "event"
    SELECTION = "selection"


class CapturedAtSource(str, Enum):
    EXIF = "exif"
    FILESYSTEM = "filesystem"
    MANUAL = "manual"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class DateCorrectionOperation(str, Enum):
    SET = "set"
    SHIFT = "shift"
    TIMEZONE = "timezone"
    CLEAR = "clear"


class DateCorrectionTargetScope(str, Enum):
    ASSET = "asset"
    FOLDER = "folder"
    EVENT = "event"
    SELECTION = "selection"
    FILTER = "filter"
