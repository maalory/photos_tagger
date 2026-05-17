from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:
    Image = None

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

DATE_KEYS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")
OFFSET_KEYS = ("OffsetTimeOriginal", "OffsetTimeDigitized", "OffsetTime")

EXIF_TAG_NAMES = {
    271: "Make",
    272: "Model",
    274: "Orientation",
    306: "DateTime",
    34853: "GPSInfo",
    36867: "DateTimeOriginal",
    36868: "DateTimeDigitized",
    36881: "OffsetTime",
    36882: "OffsetTimeOriginal",
    36883: "OffsetTimeDigitized",
    42036: "LensModel",
}

GPS_TAG_NAMES = {
    1: "GPSLatitudeRef",
    2: "GPSLatitude",
    3: "GPSLongitudeRef",
    4: "GPSLongitude",
    5: "GPSAltitudeRef",
    6: "GPSAltitude",
}


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    taken_at_original: str | None = None
    timezone_offset: str | None = None
    gps_lat: float | None = None
    gps_lng: float | None = None
    gps_alt: float | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    exif_json: str | None = None
    width: int | None = None
    height: int | None = None
    orientation: int | None = None

    def has_persistent_metadata(self) -> bool:
        return any(
            value is not None
            for value in (
                self.taken_at_original,
                self.timezone_offset,
                self.gps_lat,
                self.gps_lng,
                self.gps_alt,
                self.camera_make,
                self.camera_model,
                self.lens_model,
                self.exif_json,
            )
        )


class ExifService:
    def read_metadata(self, file_path: str) -> ExtractedMetadata:
        path = Path(file_path)
        if Image is None or path.suffix.lower() not in PHOTO_EXTENSIONS:
            return ExtractedMetadata()

        try:
            with Image.open(path) as image:
                width, height = image.size
                raw_exif = image.getexif()
        except Exception:
            return ExtractedMetadata()

        if raw_exif is None:
            raw_exif = {}

        exif_map: dict[str, Any] = {}
        gps_map: dict[str, Any] = {}

        for tag_id, value in raw_exif.items():
            tag_name = EXIF_TAG_NAMES.get(int(tag_id), str(tag_id))
            exif_map[tag_name] = _json_safe(value)
            if tag_name == "GPSInfo" and isinstance(value, dict):
                gps_map = {GPS_TAG_NAMES.get(int(key), str(key)): raw for key, raw in value.items()}

        taken_at_raw = _first_present(exif_map, DATE_KEYS)
        offset_raw = _first_present(exif_map, OFFSET_KEYS)
        timezone_offset = _normalize_offset(offset_raw)

        return ExtractedMetadata(
            taken_at_original=_normalize_exif_datetime(taken_at_raw, timezone_offset),
            timezone_offset=timezone_offset,
            gps_lat=_extract_gps_coordinate(gps_map, "GPSLatitude", "GPSLatitudeRef"),
            gps_lng=_extract_gps_coordinate(gps_map, "GPSLongitude", "GPSLongitudeRef"),
            gps_alt=_extract_gps_altitude(gps_map),
            camera_make=_normalize_string(exif_map.get("Make")),
            camera_model=_normalize_string(exif_map.get("Model")),
            lens_model=_normalize_string(exif_map.get("LensModel")),
            exif_json=_serialize_exif_payload(exif_map, gps_map),
            width=int(width) if width else None,
            height=int(height) if height else None,
            orientation=_coerce_int(exif_map.get("Orientation")),
        )



def _first_present(values: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        value = values.get(key)
        if value not in (None, ""):
            return value
    return None



def _normalize_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None



def _normalize_exif_datetime(value: Any, timezone_offset: str | None) -> str | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            break
        except ValueError:
            parsed = None
    else:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text

    if parsed is None:
        return None

    if parsed.tzinfo is None and timezone_offset is not None:
        parsed = parsed.replace(tzinfo=_timezone_from_offset(timezone_offset))
    return parsed.isoformat(timespec="seconds")



def _normalize_offset(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text == "Z":
        return "+00:00"
    if len(text) == 5 and text[0] in "+-" and text[1:].isdigit():
        return f"{text[:3]}:{text[3:]}"
    if len(text) == 6 and text[0] in "+-" and text[3] == ":" and text[1:3].isdigit() and text[4:6].isdigit():
        return text
    return None



def _timezone_from_offset(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    hours = int(offset[1:3])
    minutes = int(offset[4:6])
    delta = timedelta(hours=hours, minutes=minutes) * sign
    return timezone(delta)



def _extract_gps_coordinate(gps_map: dict[str, Any], value_key: str, ref_key: str) -> float | None:
    values = gps_map.get(value_key)
    ref = gps_map.get(ref_key)
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        return None

    try:
        degrees = _rational_to_float(values[0])
        minutes = _rational_to_float(values[1])
        seconds = _rational_to_float(values[2])
    except (TypeError, ValueError, ZeroDivisionError):
        return None

    coordinate = degrees + minutes / 60.0 + seconds / 3600.0
    if str(ref).upper() in {"S", "W"}:
        coordinate *= -1
    return round(coordinate, 6)



def _extract_gps_altitude(gps_map: dict[str, Any]) -> float | None:
    altitude = gps_map.get("GPSAltitude")
    if altitude is None:
        return None
    try:
        value = _rational_to_float(altitude)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if int(gps_map.get("GPSAltitudeRef", 0) or 0) == 1:
        value *= -1
    return round(value, 2)



def _rational_to_float(value: Any) -> float:
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return float(value.numerator) / float(value.denominator)
    if isinstance(value, tuple) and len(value) == 2:
        return float(value[0]) / float(value[1])
    return float(value)



def _coerce_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None



def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        return [int(value.numerator), int(value.denominator)]
    return str(value)



def _serialize_exif_payload(exif_map: dict[str, Any], gps_map: dict[str, Any]) -> str | None:
    payload = {key: value for key, value in exif_map.items() if value not in (None, "", [], {})}
    if gps_map:
        payload["GPSInfoDecoded"] = {key: _json_safe(value) for key, value in gps_map.items()}
    if not payload:
        return None
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
