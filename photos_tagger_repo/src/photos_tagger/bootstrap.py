from __future__ import annotations

from dataclasses import dataclass

from photos_tagger.catalog import AlbumRepository, AssetRepository, CatalogImportService, DirectoryScanner, EventRepository, FolderRepository, SourceRepository, TagRepository
from photos_tagger.config import AppPaths, build_app_paths
from photos_tagger.metadata import CapturedAtResolver, DateCorrectionRepository, DateCorrectionService, ExifService, MetadataRepository
from photos_tagger.storage.db import DatabaseManager
from photos_tagger.tagging import TaggingService


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    paths: AppPaths
    database: DatabaseManager
    source_repository: SourceRepository
    folder_repository: FolderRepository
    asset_repository: AssetRepository
    event_repository: EventRepository
    tag_repository: TagRepository
    album_repository: AlbumRepository
    metadata_repository: MetadataRepository
    date_correction_repository: DateCorrectionRepository
    directory_scanner: DirectoryScanner
    exif_service: ExifService
    captured_at_resolver: CapturedAtResolver
    catalog_import_service: CatalogImportService
    date_correction_service: DateCorrectionService
    tagging_service: TaggingService


class ApplicationBootstrap:
    def __init__(self, paths: AppPaths | None = None) -> None:
        self._paths = paths

    def build_paths(self) -> AppPaths:
        return self._paths or build_app_paths()

    def build_database(self, paths: AppPaths) -> DatabaseManager:
        return DatabaseManager(paths)

    def build_context(self) -> ApplicationContext:
        paths = self.build_paths()
        database = self.build_database(paths)
        database.initialize_schema()

        source_repository = SourceRepository(database)
        folder_repository = FolderRepository(database)
        asset_repository = AssetRepository(database)
        event_repository = EventRepository(database)
        tag_repository = TagRepository(database)
        album_repository = AlbumRepository(database)
        metadata_repository = MetadataRepository(database)
        date_correction_repository = DateCorrectionRepository(database)
        directory_scanner = DirectoryScanner()
        exif_service = ExifService()
        captured_at_resolver = CapturedAtResolver()
        catalog_import_service = CatalogImportService(
            database=database,
            source_repository=source_repository,
            folder_repository=folder_repository,
            asset_repository=asset_repository,
            directory_scanner=directory_scanner,
            metadata_repository=metadata_repository,
            date_correction_repository=date_correction_repository,
            exif_service=exif_service,
            captured_at_resolver=captured_at_resolver,
        )
        date_correction_service = DateCorrectionService(
            database=database,
            asset_repository=asset_repository,
            metadata_repository=metadata_repository,
            date_correction_repository=date_correction_repository,
            captured_at_resolver=captured_at_resolver,
        )
        tagging_service = TaggingService(
            database=database,
            asset_repository=asset_repository,
            tag_repository=tag_repository,
        )

        return ApplicationContext(
            paths=paths,
            database=database,
            source_repository=source_repository,
            folder_repository=folder_repository,
            asset_repository=asset_repository,
            event_repository=event_repository,
            tag_repository=tag_repository,
            album_repository=album_repository,
            metadata_repository=metadata_repository,
            date_correction_repository=date_correction_repository,
            directory_scanner=directory_scanner,
            exif_service=exif_service,
            captured_at_resolver=captured_at_resolver,
            catalog_import_service=catalog_import_service,
            date_correction_service=date_correction_service,
            tagging_service=tagging_service,
        )
