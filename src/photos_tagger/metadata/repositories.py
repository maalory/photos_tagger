from __future__ import annotations

import sqlite3

from photos_tagger.domain import (
    AssetDateCorrection,
    AssetMetadata,
    CapturedAtSource,
    DateCorrectionBatch,
    DateCorrectionOperation,
    DateCorrectionTargetScope,
)
from photos_tagger.metadata.exif_service import ExtractedMetadata
from photos_tagger.storage.db import DatabaseManager


class MetadataRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def get_by_asset_id(self, asset_id: int, conn: sqlite3.Connection | None = None) -> AssetMetadata | None:
        if conn is None:
            with self.database.connect() as connection:
                return self.get_by_asset_id(asset_id, connection)

        row = conn.execute(
            """
            SELECT asset_id, taken_at_original, timezone_offset, gps_lat, gps_lng, gps_alt,
                   camera_make, camera_model, lens_model, exif_json, place_id, created_at, updated_at
            FROM asset_metadata
            WHERE asset_id = ?
            """,
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        return _map_asset_metadata(row)

    def upsert_extracted_metadata(
        self,
        asset_id: int,
        extracted: ExtractedMetadata,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            """
            INSERT INTO asset_metadata (
                asset_id, taken_at_original, timezone_offset, gps_lat, gps_lng, gps_alt,
                camera_make, camera_model, lens_model, exif_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                taken_at_original = COALESCE(excluded.taken_at_original, asset_metadata.taken_at_original),
                timezone_offset = COALESCE(excluded.timezone_offset, asset_metadata.timezone_offset),
                gps_lat = COALESCE(excluded.gps_lat, asset_metadata.gps_lat),
                gps_lng = COALESCE(excluded.gps_lng, asset_metadata.gps_lng),
                gps_alt = COALESCE(excluded.gps_alt, asset_metadata.gps_alt),
                camera_make = COALESCE(excluded.camera_make, asset_metadata.camera_make),
                camera_model = COALESCE(excluded.camera_model, asset_metadata.camera_model),
                lens_model = COALESCE(excluded.lens_model, asset_metadata.lens_model),
                exif_json = COALESCE(excluded.exif_json, asset_metadata.exif_json),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                asset_id,
                extracted.taken_at_original,
                extracted.timezone_offset,
                extracted.gps_lat,
                extracted.gps_lng,
                extracted.gps_alt,
                extracted.camera_make,
                extracted.camera_model,
                extracted.lens_model,
                extracted.exif_json,
            ),
        )


class DateCorrectionRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def create_batch(
        self,
        operation_type: DateCorrectionOperation,
        target_scope: DateCorrectionTargetScope,
        parameters_json: str,
        target_selector_json: str | None,
        note: str | None,
        conn: sqlite3.Connection,
    ) -> DateCorrectionBatch:
        cursor = conn.execute(
            """
            INSERT INTO date_correction_batches (
                operation_type, target_scope, target_selector_json, parameters_json, note
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (operation_type.value, target_scope.value, target_selector_json, parameters_json, note),
        )
        batch_id = int(cursor.lastrowid)
        row = conn.execute(
            """
            SELECT id, operation_type, target_scope, target_selector_json, parameters_json, note, created_at
            FROM date_correction_batches
            WHERE id = ?
            """,
            (batch_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Nepodarilo se nacist batch korekce {batch_id}.")
        return _map_date_correction_batch(row)

    def get_active_for_asset(
        self,
        asset_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> AssetDateCorrection | None:
        if conn is None:
            with self.database.connect() as connection:
                return self.get_active_for_asset(asset_id, connection)

        row = conn.execute(
            """
            SELECT id, asset_id, batch_id, correction_mode, manual_captured_at, shift_minutes,
                   timezone_offset_override, previous_captured_at, new_captured_at,
                   previous_source, new_source, note, is_active, applied_at
            FROM asset_date_corrections
            WHERE asset_id = ? AND is_active = 1
            ORDER BY applied_at DESC, id DESC
            LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        return _map_asset_date_correction(row)

    def deactivate_active_for_assets(self, asset_ids: list[int], conn: sqlite3.Connection) -> None:
        if not asset_ids:
            return
        placeholders = ", ".join("?" for _ in asset_ids)
        conn.execute(
            f"UPDATE asset_date_corrections SET is_active = 0 WHERE asset_id IN ({placeholders}) AND is_active = 1",
            asset_ids,
        )

    def insert_correction(
        self,
        asset_id: int,
        batch_id: int | None,
        correction_mode: DateCorrectionOperation,
        manual_captured_at: str | None,
        shift_minutes: int | None,
        timezone_offset_override: str | None,
        previous_captured_at: str | None,
        new_captured_at: str | None,
        previous_source: CapturedAtSource | None,
        new_source: CapturedAtSource,
        note: str | None,
        is_active: bool,
        conn: sqlite3.Connection,
    ) -> AssetDateCorrection:
        cursor = conn.execute(
            """
            INSERT INTO asset_date_corrections (
                asset_id, batch_id, correction_mode, manual_captured_at, shift_minutes,
                timezone_offset_override, previous_captured_at, new_captured_at,
                previous_source, new_source, note, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asset_id,
                batch_id,
                correction_mode.value,
                manual_captured_at,
                shift_minutes,
                timezone_offset_override,
                previous_captured_at,
                new_captured_at,
                previous_source.value if previous_source is not None else None,
                new_source.value,
                note,
                1 if is_active else 0,
            ),
        )
        correction_id = int(cursor.lastrowid)
        row = conn.execute(
            """
            SELECT id, asset_id, batch_id, correction_mode, manual_captured_at, shift_minutes,
                   timezone_offset_override, previous_captured_at, new_captured_at,
                   previous_source, new_source, note, is_active, applied_at
            FROM asset_date_corrections
            WHERE id = ?
            """,
            (correction_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Nepodarilo se nacist korekci data {correction_id}.")
        return _map_asset_date_correction(row)



def _map_asset_metadata(row: sqlite3.Row) -> AssetMetadata:
    return AssetMetadata(
        asset_id=int(row["asset_id"]),
        taken_at_original=row["taken_at_original"],
        timezone_offset=row["timezone_offset"],
        gps_lat=row["gps_lat"],
        gps_lng=row["gps_lng"],
        gps_alt=row["gps_alt"],
        camera_make=row["camera_make"],
        camera_model=row["camera_model"],
        lens_model=row["lens_model"],
        exif_json=row["exif_json"],
        place_id=row["place_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )



def _map_date_correction_batch(row: sqlite3.Row) -> DateCorrectionBatch:
    return DateCorrectionBatch(
        id=int(row["id"]),
        operation_type=DateCorrectionOperation(str(row["operation_type"])),
        target_scope=DateCorrectionTargetScope(str(row["target_scope"])),
        target_selector_json=row["target_selector_json"],
        parameters_json=str(row["parameters_json"]),
        note=row["note"],
        created_at=row["created_at"],
    )



def _map_asset_date_correction(row: sqlite3.Row) -> AssetDateCorrection:
    previous_source = row["previous_source"]
    return AssetDateCorrection(
        id=int(row["id"]),
        asset_id=int(row["asset_id"]),
        batch_id=row["batch_id"],
        correction_mode=DateCorrectionOperation(str(row["correction_mode"])),
        manual_captured_at=row["manual_captured_at"],
        shift_minutes=row["shift_minutes"],
        timezone_offset_override=row["timezone_offset_override"],
        previous_captured_at=row["previous_captured_at"],
        new_captured_at=row["new_captured_at"],
        previous_source=CapturedAtSource(str(previous_source)) if previous_source is not None else None,
        new_source=CapturedAtSource(str(row["new_source"])),
        note=row["note"],
        is_active=bool(row["is_active"]),
        applied_at=row["applied_at"],
    )
