from __future__ import annotations

from dataclasses import dataclass

from photos_tagger.domain.enums import (
    AlbumType,
    CapturedAtSource,
    DateCorrectionOperation,
    DateCorrectionTargetScope,
    GroupingMode,
    MediaType,
    TagScope,
)


@dataclass(frozen=True, slots=True)
class Source:
    id: int
    name: str
    root_path: str
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Folder:
    id: int
    source_id: int
    parent_id: int | None
    relative_path: str
    absolute_path: str
    folder_name: str
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Asset:
    id: int
    source_id: int
    folder_id: int | None
    event_id: int | None
    file_name: str
    extension: str | None
    relative_path: str
    absolute_path: str
    media_type: MediaType
    file_size: int | None
    checksum_sha256: str | None
    captured_at: str | None
    modified_at_fs: str | None
    imported_at: str | None
    width: int | None
    height: int | None
    orientation: int | None
    rating: int
    is_favorite: bool
    is_rejected: bool
    captured_at_source: CapturedAtSource = CapturedAtSource.UNKNOWN


@dataclass(frozen=True, slots=True)
class Place:
    id: int
    provider: str
    country_code: str | None
    country_name: str | None
    region_name: str | None
    city_name: str | None
    locality_name: str | None
    latitude: float | None
    longitude: float | None
    geohash: str | None
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class AssetMetadata:
    asset_id: int
    taken_at_original: str | None
    timezone_offset: str | None
    gps_lat: float | None
    gps_lng: float | None
    gps_alt: float | None
    camera_make: str | None
    camera_model: str | None
    lens_model: str | None
    exif_json: str | None
    place_id: int | None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    source_id: int
    folder_id: int | None
    title: str | None
    start_at: str | None
    end_at: str | None
    inferred_place_name: str | None
    grouping_mode: GroupingMode
    user_locked: bool
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class Tag:
    id: int
    name: str
    slug: str
    category: str | None
    color: str | None
    description: str | None
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class TagShortcut:
    id: int
    key_sequence: str
    tag_id: int
    scope: TagScope
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class Album:
    id: int
    name: str
    album_type: AlbumType
    description: str | None
    sort_order: str
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True, slots=True)
class AlbumRule:
    id: int
    album_id: int
    rule_json: str
    is_enabled: bool
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class DateCorrectionBatch:
    id: int
    operation_type: DateCorrectionOperation
    target_scope: DateCorrectionTargetScope
    target_selector_json: str | None
    parameters_json: str
    note: str | None
    created_at: str | None = None


@dataclass(frozen=True, slots=True)
class AssetDateCorrection:
    id: int
    asset_id: int
    batch_id: int | None
    correction_mode: DateCorrectionOperation
    manual_captured_at: str | None
    shift_minutes: int | None
    timezone_offset_override: str | None
    previous_captured_at: str | None
    new_captured_at: str | None
    previous_source: CapturedAtSource | None
    new_source: CapturedAtSource
    note: str | None
    is_active: bool
    applied_at: str | None = None
