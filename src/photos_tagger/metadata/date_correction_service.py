from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json

from photos_tagger.catalog.repositories import AssetRepository
from photos_tagger.domain import (
    CapturedAtSource,
    DateCorrectionBatch,
    DateCorrectionOperation,
    DateCorrectionTargetScope,
)
from photos_tagger.metadata.captured_at_resolver import CapturedAtResolver, ResolvedCapturedAt
from photos_tagger.metadata.repositories import DateCorrectionRepository, MetadataRepository
from photos_tagger.storage.db import DatabaseManager


@dataclass(frozen=True, slots=True)
class DateCorrectionSummary:
    batch: DateCorrectionBatch | None
    requested_asset_count: int
    updated_asset_count: int
    skipped_asset_count: int


@dataclass(frozen=True, slots=True)
class _CorrectionPayload:
    correction_mode: DateCorrectionOperation
    manual_captured_at: str | None
    shift_minutes: int | None
    timezone_offset_override: str | None
    new_captured_at: str | None
    new_source: CapturedAtSource
    is_active: bool


class DateCorrectionService:
    def __init__(
        self,
        database: DatabaseManager,
        asset_repository: AssetRepository,
        metadata_repository: MetadataRepository,
        date_correction_repository: DateCorrectionRepository,
        captured_at_resolver: CapturedAtResolver,
    ) -> None:
        self.database = database
        self.asset_repository = asset_repository
        self.metadata_repository = metadata_repository
        self.date_correction_repository = date_correction_repository
        self.captured_at_resolver = captured_at_resolver

    def apply_fixed_datetime(
        self,
        asset_ids: list[int],
        captured_at: str,
        note: str | None = None,
    ) -> DateCorrectionSummary:
        normalized_captured_at = _normalize_datetime_value(captured_at)
        return self._apply(
            asset_ids=asset_ids,
            operation_type=DateCorrectionOperation.SET,
            parameters={"captured_at": normalized_captured_at},
            note=note,
            builder=lambda current_effective: _CorrectionPayload(
                correction_mode=DateCorrectionOperation.SET,
                manual_captured_at=normalized_captured_at,
                shift_minutes=None,
                timezone_offset_override=None,
                new_captured_at=normalized_captured_at,
                new_source=CapturedAtSource.MANUAL,
                is_active=True,
            ),
        )

    def apply_shift(
        self,
        asset_ids: list[int],
        shift_minutes: int,
        note: str | None = None,
    ) -> DateCorrectionSummary:
        return self._apply(
            asset_ids=asset_ids,
            operation_type=DateCorrectionOperation.SHIFT,
            parameters={"shift_minutes": int(shift_minutes)},
            note=note,
            builder=lambda current_effective: None
            if current_effective.captured_at is None
            else _CorrectionPayload(
                correction_mode=DateCorrectionOperation.SHIFT,
                manual_captured_at=None,
                shift_minutes=int(shift_minutes),
                timezone_offset_override=None,
                new_captured_at=_shift_datetime_value(current_effective.captured_at, int(shift_minutes)),
                new_source=CapturedAtSource.DERIVED,
                is_active=True,
            ),
        )

    def apply_timezone_override(
        self,
        asset_ids: list[int],
        timezone_offset: str,
        note: str | None = None,
    ) -> DateCorrectionSummary:
        normalized_offset = _normalize_timezone_offset(timezone_offset)
        return self._apply(
            asset_ids=asset_ids,
            operation_type=DateCorrectionOperation.TIMEZONE,
            parameters={"timezone_offset": normalized_offset},
            note=note,
            builder=lambda current_effective: None
            if current_effective.captured_at is None
            else _CorrectionPayload(
                correction_mode=DateCorrectionOperation.TIMEZONE,
                manual_captured_at=None,
                shift_minutes=None,
                timezone_offset_override=normalized_offset,
                new_captured_at=_apply_timezone_override(current_effective.captured_at, normalized_offset),
                new_source=CapturedAtSource.DERIVED,
                is_active=True,
            ),
        )

    def clear_manual_override(
        self,
        asset_ids: list[int],
        note: str | None = None,
    ) -> DateCorrectionSummary:
        return self._apply_clear(asset_ids=asset_ids, note=note)

    def _apply(
        self,
        asset_ids: list[int],
        operation_type: DateCorrectionOperation,
        parameters: dict[str, object],
        note: str | None,
        builder,
    ) -> DateCorrectionSummary:
        normalized_ids = _normalize_asset_ids(asset_ids)
        if not normalized_ids:
            return DateCorrectionSummary(None, 0, 0, 0)

        with self.database.connect() as conn:
            batch = self.date_correction_repository.create_batch(
                operation_type=operation_type,
                target_scope=DateCorrectionTargetScope.SELECTION,
                parameters_json=json.dumps(parameters, ensure_ascii=False, sort_keys=True),
                target_selector_json=json.dumps({"asset_ids": normalized_ids}, ensure_ascii=False, sort_keys=True),
                note=note,
                conn=conn,
            )

            updated_count = 0
            skipped_count = 0

            for asset_id in normalized_ids:
                asset = self.asset_repository.get_by_id(asset_id, conn)
                if asset is None:
                    skipped_count += 1
                    continue

                metadata = self.metadata_repository.get_by_asset_id(asset_id, conn)
                active_correction = self.date_correction_repository.get_active_for_asset(asset_id, conn)
                current_effective = self.captured_at_resolver.resolve_effective(
                    taken_at_original=metadata.taken_at_original if metadata is not None else None,
                    modified_at_fs=asset.modified_at_fs,
                    active_correction=active_correction,
                )

                payload = builder(current_effective)
                if payload is None:
                    skipped_count += 1
                    continue

                self.date_correction_repository.deactivate_active_for_assets([asset_id], conn)
                self.date_correction_repository.insert_correction(
                    asset_id=asset_id,
                    batch_id=batch.id,
                    correction_mode=payload.correction_mode,
                    manual_captured_at=payload.manual_captured_at,
                    shift_minutes=payload.shift_minutes,
                    timezone_offset_override=payload.timezone_offset_override,
                    previous_captured_at=current_effective.captured_at,
                    new_captured_at=payload.new_captured_at,
                    previous_source=current_effective.source,
                    new_source=payload.new_source,
                    note=note,
                    is_active=payload.is_active,
                    conn=conn,
                )
                self.asset_repository.update_effective_capture(
                    asset_id=asset_id,
                    captured_at=payload.new_captured_at,
                    captured_at_source=payload.new_source,
                    conn=conn,
                )
                updated_count += 1

            conn.commit()

        return DateCorrectionSummary(
            batch=batch,
            requested_asset_count=len(normalized_ids),
            updated_asset_count=updated_count,
            skipped_asset_count=skipped_count,
        )

    def _apply_clear(self, asset_ids: list[int], note: str | None) -> DateCorrectionSummary:
        normalized_ids = _normalize_asset_ids(asset_ids)
        if not normalized_ids:
            return DateCorrectionSummary(None, 0, 0, 0)

        with self.database.connect() as conn:
            batch = self.date_correction_repository.create_batch(
                operation_type=DateCorrectionOperation.CLEAR,
                target_scope=DateCorrectionTargetScope.SELECTION,
                parameters_json=json.dumps({"clear": True}, sort_keys=True),
                target_selector_json=json.dumps({"asset_ids": normalized_ids}, sort_keys=True),
                note=note,
                conn=conn,
            )

            updated_count = 0
            skipped_count = 0

            for asset_id in normalized_ids:
                asset = self.asset_repository.get_by_id(asset_id, conn)
                if asset is None:
                    skipped_count += 1
                    continue

                metadata = self.metadata_repository.get_by_asset_id(asset_id, conn)
                active_correction = self.date_correction_repository.get_active_for_asset(asset_id, conn)
                if active_correction is None:
                    skipped_count += 1
                    continue

                current_effective = self.captured_at_resolver.resolve_effective(
                    taken_at_original=metadata.taken_at_original if metadata is not None else None,
                    modified_at_fs=asset.modified_at_fs,
                    active_correction=active_correction,
                )
                base_effective = self.captured_at_resolver.resolve_base(
                    taken_at_original=metadata.taken_at_original if metadata is not None else None,
                    modified_at_fs=asset.modified_at_fs,
                )

                self.date_correction_repository.deactivate_active_for_assets([asset_id], conn)
                self.date_correction_repository.insert_correction(
                    asset_id=asset_id,
                    batch_id=batch.id,
                    correction_mode=DateCorrectionOperation.CLEAR,
                    manual_captured_at=None,
                    shift_minutes=None,
                    timezone_offset_override=None,
                    previous_captured_at=current_effective.captured_at,
                    new_captured_at=base_effective.captured_at,
                    previous_source=current_effective.source,
                    new_source=base_effective.source,
                    note=note,
                    is_active=False,
                    conn=conn,
                )
                self.asset_repository.update_effective_capture(
                    asset_id=asset_id,
                    captured_at=base_effective.captured_at,
                    captured_at_source=base_effective.source,
                    conn=conn,
                )
                updated_count += 1

            conn.commit()

        return DateCorrectionSummary(
            batch=batch,
            requested_asset_count=len(normalized_ids),
            updated_asset_count=updated_count,
            skipped_asset_count=skipped_count,
        )



def _normalize_asset_ids(asset_ids: list[int]) -> list[int]:
    ordered: list[int] = []
    seen: set[int] = set()
    for asset_id in asset_ids:
        normalized = int(asset_id)
        if normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)
    return ordered



def _normalize_datetime_value(value: str) -> str:
    parsed = _parse_datetime_value(value)
    return parsed.isoformat(timespec="seconds")



def _shift_datetime_value(value: str, shift_minutes: int) -> str:
    parsed = _parse_datetime_value(value)
    return (parsed + timedelta(minutes=shift_minutes)).isoformat(timespec="seconds")



def _apply_timezone_override(value: str, timezone_offset: str) -> str:
    parsed = _parse_datetime_value(value)
    target_timezone = _timezone_from_offset(timezone_offset)
    if parsed.tzinfo is None:
        adjusted = parsed.replace(tzinfo=target_timezone)
    else:
        adjusted = parsed.astimezone(target_timezone)
    return adjusted.isoformat(timespec="seconds")



def _parse_datetime_value(value: str) -> datetime:
    return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))



def _normalize_timezone_offset(value: str) -> str:
    text = value.strip()
    if text == "Z":
        return "+00:00"
    if len(text) == 5 and text[0] in "+-" and text[1:].isdigit():
        return f"{text[:3]}:{text[3:]}"
    if len(text) == 6 and text[0] in "+-" and text[3] == ":" and text[1:3].isdigit() and text[4:6].isdigit():
        return text
    raise ValueError(f"Neplatny timezone offset: {value}")



def _timezone_from_offset(offset: str) -> timezone:
    sign = 1 if offset[0] == "+" else -1
    hours = int(offset[1:3])
    minutes = int(offset[4:6])
    return timezone(sign * timedelta(hours=hours, minutes=minutes))
