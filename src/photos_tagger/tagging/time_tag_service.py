from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from photos_tagger.catalog.repositories import AssetRepository, TagRepository
from photos_tagger.storage.db import DatabaseManager

YEAR_TAG_PATTERN = re.compile(r"^rok:(\d{4})$")
MONTH_TAG_PATTERN = re.compile(r"^mesic:(\d{4})-(\d{2})$")
DATE_PREFIX_PATTERN = re.compile(r"^(\d{4})[:\-.](\d{2})")


@dataclass(frozen=True, slots=True)
class TimeTagUpdateSummary:
    mode: str
    requested_asset_count: int
    processed_asset_count: int
    updated_asset_count: int
    skipped_asset_count: int

    @property
    def message(self) -> str:
        return (
            f"Datum tagy ({self.mode}): zpracovano {self.processed_asset_count}/{self.requested_asset_count}, "
            f"zmeneno {self.updated_asset_count}, preskoceno {self.skipped_asset_count}."
        )


class TimeTagService:
    def __init__(
        self,
        database: DatabaseManager,
        asset_repository: AssetRepository,
        tag_repository: TagRepository,
    ) -> None:
        self.database = database
        self.asset_repository = asset_repository
        self.tag_repository = tag_repository

    def sync_time_tags_for_assets(
        self,
        asset_ids: list[int],
        assigned_via: str = "import",
    ) -> TimeTagUpdateSummary:
        normalized_ids = _normalize_asset_ids(asset_ids)
        if not normalized_ids:
            return TimeTagUpdateSummary(
                mode="auto",
                requested_asset_count=0,
                processed_asset_count=0,
                updated_asset_count=0,
                skipped_asset_count=0,
            )

        with self.database.connect() as conn:
            assets = self.asset_repository.list_by_ids(normalized_ids, conn)
            overrides = self.tag_repository.get_time_tag_overrides([asset.id for asset in assets], conn)

            updated_count = 0
            for asset in assets:
                year_tag, month_tag = _desired_tags_from_asset(asset.captured_at, overrides.get(asset.id))
                changed = self._apply_time_tags(
                    asset_id=asset.id,
                    year_tag=year_tag,
                    month_tag=month_tag,
                    assigned_via=assigned_via,
                    conn=conn,
                )
                if changed:
                    updated_count += 1

            conn.commit()

        processed_count = len(assets)
        skipped_count = len(normalized_ids) - processed_count
        skipped_count += processed_count - updated_count
        return TimeTagUpdateSummary(
            mode="auto",
            requested_asset_count=len(normalized_ids),
            processed_asset_count=processed_count,
            updated_asset_count=updated_count,
            skipped_asset_count=max(0, skipped_count),
        )

    def set_manual_time_tags(
        self,
        asset_ids: list[int],
        year: int,
        month: int | None = None,
        assigned_via: str = "bulk",
    ) -> TimeTagUpdateSummary:
        normalized_ids = _normalize_asset_ids(asset_ids)
        if not normalized_ids:
            return TimeTagUpdateSummary(
                mode="manual",
                requested_asset_count=0,
                processed_asset_count=0,
                updated_asset_count=0,
                skipped_asset_count=0,
            )

        normalized_year = _normalize_year(year)
        normalized_month = _normalize_month(month)
        year_tag = f"rok:{normalized_year:04d}"
        month_tag = f"mesic:{normalized_year:04d}-{normalized_month:02d}" if normalized_month is not None else None

        with self.database.connect() as conn:
            assets = self.asset_repository.list_by_ids(normalized_ids, conn)
            updated_count = 0

            for asset in assets:
                self.tag_repository.set_time_tag_override(
                    asset_id=asset.id,
                    mode="manual",
                    manual_year=normalized_year,
                    manual_month=normalized_month,
                    conn=conn,
                )
                changed = self._apply_time_tags(
                    asset_id=asset.id,
                    year_tag=year_tag,
                    month_tag=month_tag,
                    assigned_via=assigned_via,
                    conn=conn,
                )
                if changed:
                    updated_count += 1

            conn.commit()

        processed_count = len(assets)
        skipped_count = len(normalized_ids) - processed_count
        skipped_count += processed_count - updated_count
        mode = "manual_rok_a_mesic" if normalized_month is not None else "manual_rok"
        return TimeTagUpdateSummary(
            mode=mode,
            requested_asset_count=len(normalized_ids),
            processed_asset_count=processed_count,
            updated_asset_count=updated_count,
            skipped_asset_count=max(0, skipped_count),
        )

    def set_auto_time_tags(
        self,
        asset_ids: list[int],
        assigned_via: str = "bulk",
    ) -> TimeTagUpdateSummary:
        normalized_ids = _normalize_asset_ids(asset_ids)
        if not normalized_ids:
            return TimeTagUpdateSummary(
                mode="auto",
                requested_asset_count=0,
                processed_asset_count=0,
                updated_asset_count=0,
                skipped_asset_count=0,
            )

        with self.database.connect() as conn:
            assets = self.asset_repository.list_by_ids(normalized_ids, conn)
            existing_ids = [asset.id for asset in assets]
            self.tag_repository.delete_time_tag_overrides(existing_ids, conn)

            updated_count = 0
            for asset in assets:
                year_tag, month_tag = _desired_tags_from_asset(asset.captured_at, None)
                changed = self._apply_time_tags(
                    asset_id=asset.id,
                    year_tag=year_tag,
                    month_tag=month_tag,
                    assigned_via=assigned_via,
                    conn=conn,
                )
                if changed:
                    updated_count += 1

            conn.commit()

        processed_count = len(assets)
        skipped_count = len(normalized_ids) - processed_count
        skipped_count += processed_count - updated_count
        return TimeTagUpdateSummary(
            mode="auto",
            requested_asset_count=len(normalized_ids),
            processed_asset_count=processed_count,
            updated_asset_count=updated_count,
            skipped_asset_count=max(0, skipped_count),
        )

    def _apply_time_tags(
        self,
        asset_id: int,
        year_tag: str | None,
        month_tag: str | None,
        assigned_via: str,
        conn,
    ) -> bool:
        current_tags = self.tag_repository.list_direct_asset_tags(asset_id, conn)
        managed_current = {tag.id: tag for tag in current_tags if _is_managed_time_tag(tag.name)}
        current_managed_ids = set(managed_current.keys())

        desired_names = [name for name in (year_tag, month_tag) if name]
        desired_tags = [self.tag_repository.get_or_create_tag(name, conn) for name in desired_names]
        desired_ids = {tag.id for tag in desired_tags}

        changed = False
        for tag_id in sorted(current_managed_ids - desired_ids):
            self.tag_repository.set_asset_tag_assignment(
                asset_id=asset_id,
                tag_id=tag_id,
                is_assigned=False,
                assigned_via=assigned_via,
                conn=conn,
            )
            changed = True

        for tag_id in sorted(desired_ids - current_managed_ids):
            self.tag_repository.set_asset_tag_assignment(
                asset_id=asset_id,
                tag_id=tag_id,
                is_assigned=True,
                assigned_via=assigned_via,
                conn=conn,
            )
            changed = True

        return changed


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


def _normalize_year(value: int) -> int:
    year = int(value)
    if year < 1 or year > 9999:
        raise ValueError(f"Neplatny rok: {value}")
    return year


def _normalize_month(value: int | None) -> int | None:
    if value is None:
        return None
    month = int(value)
    if month < 1 or month > 12:
        raise ValueError(f"Neplatny mesic: {value}")
    return month


def _desired_tags_from_asset(
    captured_at: str | None,
    override: tuple[str, int | None, int | None] | None,
) -> tuple[str | None, str | None]:
    if override is not None:
        mode, manual_year, manual_month = override
        if mode == "manual" and manual_year is not None:
            normalized_month = _normalize_month(manual_month)
            year_tag = f"rok:{manual_year:04d}"
            month_tag = (
                f"mesic:{manual_year:04d}-{normalized_month:02d}" if normalized_month is not None else None
            )
            return year_tag, month_tag

    year, month = _parse_year_month(captured_at)
    if year is None:
        return None, None
    year_tag = f"rok:{year:04d}"
    month_tag = f"mesic:{year:04d}-{month:02d}" if month is not None else None
    return year_tag, month_tag


def _parse_year_month(captured_at: str | None) -> tuple[int | None, int | None]:
    if not captured_at:
        return None, None

    text = captured_at.strip()
    if not text:
        return None, None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return int(parsed.year), int(parsed.month)
    except ValueError:
        pass

    match = DATE_PREFIX_PATTERN.match(text)
    if match is None:
        return None, None

    year = int(match.group(1))
    month = int(match.group(2))
    if month < 1 or month > 12:
        return None, None
    return year, month


def _is_managed_time_tag(tag_name: str) -> bool:
    normalized = tag_name.strip()
    return YEAR_TAG_PATTERN.match(normalized) is not None or MONTH_TAG_PATTERN.match(normalized) is not None
