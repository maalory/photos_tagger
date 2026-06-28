from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from photos_tagger.catalog.repositories import AssetRepository, FolderRepository, SourceRepository
from photos_tagger.catalog.scan_service import DirectoryScanner
from photos_tagger.domain import Source
from photos_tagger.metadata.captured_at_resolver import CapturedAtResolver
from photos_tagger.metadata.exif_service import ExifService
from photos_tagger.metadata.repositories import DateCorrectionRepository, MetadataRepository
from photos_tagger.storage.db import DatabaseManager


class SourceNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CatalogImportSummary:
    source: Source
    scanned_folder_count: int
    scanned_asset_count: int


class CatalogImportService:
    def __init__(
        self,
        database: DatabaseManager,
        source_repository: SourceRepository,
        folder_repository: FolderRepository,
        asset_repository: AssetRepository,
        directory_scanner: DirectoryScanner,
        metadata_repository: MetadataRepository,
        date_correction_repository: DateCorrectionRepository,
        exif_service: ExifService,
        captured_at_resolver: CapturedAtResolver,
        on_assets_imported: Callable[[list[int]], None] | None = None,
    ) -> None:
        self.database = database
        self.source_repository = source_repository
        self.folder_repository = folder_repository
        self.asset_repository = asset_repository
        self.directory_scanner = directory_scanner
        self.metadata_repository = metadata_repository
        self.date_correction_repository = date_correction_repository
        self.exif_service = exif_service
        self.captured_at_resolver = captured_at_resolver
        self.on_assets_imported = on_assets_imported

    def import_source(self, source_id: int) -> CatalogImportSummary:
        source = self.source_repository.get_by_id(source_id)
        if source is None:
            raise SourceNotFoundError(f"Zdroj s ID {source_id} neexistuje.")

        scan_result = self.directory_scanner.scan_source(source.root_path)

        with self.database.connect() as conn:
            self.source_repository.touch(source.id, conn)
            folder_id_map = self.folder_repository.upsert_scanned_folders(source.id, scan_result.folders, conn)
            asset_id_map = self.asset_repository.upsert_scanned_assets(source.id, scan_result.assets, folder_id_map, conn)

            for scanned_asset in scan_result.assets:
                asset_id = asset_id_map[scanned_asset.relative_path]
                extracted = self.exif_service.read_metadata(scanned_asset.absolute_path)
                self.metadata_repository.upsert_extracted_metadata(asset_id, extracted, conn)
                persisted_metadata = self.metadata_repository.get_by_asset_id(asset_id, conn)

                active_correction = self.date_correction_repository.get_active_for_asset(asset_id, conn)
                effective_capture = self.captured_at_resolver.resolve_effective(
                    taken_at_original=persisted_metadata.taken_at_original if persisted_metadata is not None else None,
                    modified_at_fs=scanned_asset.modified_at_fs,
                    active_correction=active_correction,
                )
                self.asset_repository.update_metadata_projection(
                    asset_id=asset_id,
                    width=extracted.width,
                    height=extracted.height,
                    orientation=extracted.orientation,
                    conn=conn,
                )
                self.asset_repository.update_effective_capture(
                    asset_id=asset_id,
                    captured_at=effective_capture.captured_at,
                    captured_at_source=effective_capture.source,
                    conn=conn,
                )

            conn.commit()

        if self.on_assets_imported is not None:
            imported_asset_ids = [asset_id_map[asset.relative_path] for asset in scan_result.assets]
            self.on_assets_imported(imported_asset_ids)

        return CatalogImportSummary(
            source=source,
            scanned_folder_count=len(scan_result.folders),
            scanned_asset_count=len(scan_result.assets),
        )
