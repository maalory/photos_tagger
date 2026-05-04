from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import unicodedata

from photos_tagger.catalog.scan_service import ScannedAsset, ScannedFolder
from photos_tagger.domain import (
    Album,
    AlbumType,
    Asset,
    CapturedAtSource,
    Event,
    Folder,
    GroupingMode,
    MediaType,
    Source,
    Tag,
    TagScope,
    TagShortcut,
)
from photos_tagger.storage.db import DatabaseManager


class RepositoryError(RuntimeError):
    pass


class DuplicateSourceError(RepositoryError):
    pass


class BaseRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    @staticmethod
    def _count(conn: sqlite3.Connection, table_name: str) -> int:
        row = conn.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        if row is None:
            return 0
        return int(row["count"])


class SourceRepository(BaseRepository):
    def list_sources(self) -> list[Source]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, root_path, is_active, created_at, updated_at
                FROM sources
                ORDER BY root_path COLLATE NOCASE
                """
            ).fetchall()
        return [_map_source(row) for row in rows]

    def get_by_id(self, source_id: int) -> Source | None:
        with self.database.connect() as conn:
            return self._get_by_id(conn, source_id)

    def add_source(self, root_path: str, name: str | None = None) -> Source:
        normalized_path = self._normalize_root_path(root_path)
        source_name = name or self._derive_name(normalized_path)

        try:
            with self.database.connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO sources (name, root_path) VALUES (?, ?)",
                    (source_name, normalized_path),
                )
                source_id = int(cursor.lastrowid)
                conn.commit()
        except sqlite3.IntegrityError as exc:
            raise DuplicateSourceError(f"Zdroj '{normalized_path}' uz v katalogu existuje.") from exc

        created = self.get_by_id(source_id)
        if created is None:
            raise RepositoryError("Zdroj byl vlozen, ale nepodarilo se ho znovu nacist.")
        return created

    def touch(self, source_id: int, conn: sqlite3.Connection) -> None:
        conn.execute(
            "UPDATE sources SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (source_id,),
        )

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "sources")

    def _get_by_id(self, conn: sqlite3.Connection, source_id: int) -> Source | None:
        row = conn.execute(
            """
            SELECT id, name, root_path, is_active, created_at, updated_at
            FROM sources
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            return None
        return _map_source(row)

    @staticmethod
    def _normalize_root_path(root_path: str) -> str:
        path = Path(root_path).expanduser()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Zdrojova slozka neexistuje nebo neni adresar: {root_path}")
        return str(path.resolve())

    @staticmethod
    def _derive_name(root_path: str) -> str:
        path = Path(root_path)
        return path.name or root_path


class FolderRepository(BaseRepository):
    def list_by_source(self, source_id: int) -> list[Folder]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source_id, parent_id, relative_path, absolute_path, folder_name, created_at, updated_at
                FROM folders
                WHERE source_id = ?
                ORDER BY relative_path COLLATE NOCASE
                """,
                (source_id,),
            ).fetchall()
        return [_map_folder(row) for row in rows]

    def upsert_scanned_folders(
        self,
        source_id: int,
        folders: list[ScannedFolder],
        conn: sqlite3.Connection,
    ) -> dict[str, int]:
        folder_id_map: dict[str, int] = {}
        sorted_folders = sorted(folders, key=lambda item: (item.relative_path.count("/"), item.relative_path))

        for folder in sorted_folders:
            parent_id = None
            if folder.parent_relative_path is not None:
                parent_id = folder_id_map.get(folder.parent_relative_path)

            conn.execute(
                """
                INSERT INTO folders (source_id, parent_id, relative_path, absolute_path, folder_name)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id, relative_path) DO UPDATE SET
                    parent_id = excluded.parent_id,
                    absolute_path = excluded.absolute_path,
                    folder_name = excluded.folder_name,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (source_id, parent_id, folder.relative_path, folder.absolute_path, folder.folder_name),
            )
            row = conn.execute(
                "SELECT id FROM folders WHERE source_id = ? AND relative_path = ?",
                (source_id, folder.relative_path),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"Nepodarilo se nacist folder '{folder.relative_path}' po upsertu.")
            folder_id_map[folder.relative_path] = int(row["id"])

        return folder_id_map

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "folders")


class AssetRepository(BaseRepository):
    def list_by_folder(self, folder_id: int) -> list[Asset]:
        with self.database.connect() as conn:
            rows = conn.execute(
                _asset_select_sql() + " WHERE folder_id = ? ORDER BY captured_at, file_name COLLATE NOCASE",
                (folder_id,),
            ).fetchall()
        return [_map_asset(row) for row in rows]

    def get_by_id(self, asset_id: int, conn: sqlite3.Connection | None = None) -> Asset | None:
        if conn is None:
            with self.database.connect() as connection:
                return self.get_by_id(asset_id, connection)

        row = conn.execute(
            _asset_select_sql() + " WHERE id = ?",
            (asset_id,),
        ).fetchone()
        if row is None:
            return None
        return _map_asset(row)

    def list_by_ids(self, asset_ids: list[int], conn: sqlite3.Connection | None = None) -> list[Asset]:
        normalized_ids = [int(asset_id) for asset_id in asset_ids]
        if not normalized_ids:
            return []

        if conn is None:
            with self.database.connect() as connection:
                return self.list_by_ids(normalized_ids, connection)

        placeholders = ", ".join("?" for _ in normalized_ids)
        rows = conn.execute(
            _asset_select_sql() + f" WHERE id IN ({placeholders})",
            normalized_ids,
        ).fetchall()
        assets_by_id = {asset.id: asset for asset in (_map_asset(row) for row in rows)}
        return [assets_by_id[asset_id] for asset_id in normalized_ids if asset_id in assets_by_id]

    def upsert_scanned_assets(
        self,
        source_id: int,
        assets: list[ScannedAsset],
        folder_id_map: dict[str, int],
        conn: sqlite3.Connection,
    ) -> dict[str, int]:
        asset_id_map: dict[str, int] = {}

        for asset in assets:
            folder_id = folder_id_map.get(asset.folder_relative_path)
            if folder_id is None:
                raise RepositoryError(
                    f"Pro asset '{asset.relative_path}' chybi folder '{asset.folder_relative_path}' v mape folderu."
                )

            conn.execute(
                """
                INSERT INTO assets (
                    source_id, folder_id, file_name, extension, relative_path, absolute_path,
                    media_type, file_size, modified_at_fs
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, relative_path) DO UPDATE SET
                    folder_id = excluded.folder_id,
                    file_name = excluded.file_name,
                    extension = excluded.extension,
                    absolute_path = excluded.absolute_path,
                    media_type = excluded.media_type,
                    file_size = excluded.file_size,
                    modified_at_fs = excluded.modified_at_fs
                """,
                (
                    source_id,
                    folder_id,
                    asset.file_name,
                    asset.extension,
                    asset.relative_path,
                    asset.absolute_path,
                    asset.media_type.value,
                    asset.file_size,
                    asset.modified_at_fs,
                ),
            )
            row = conn.execute(
                "SELECT id FROM assets WHERE source_id = ? AND relative_path = ?",
                (source_id, asset.relative_path),
            ).fetchone()
            if row is None:
                raise RepositoryError(f"Nepodarilo se nacist asset '{asset.relative_path}' po upsertu.")
            asset_id_map[asset.relative_path] = int(row["id"])

        return asset_id_map

    def update_metadata_projection(
        self,
        asset_id: int,
        width: int | None,
        height: int | None,
        orientation: int | None,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            """
            UPDATE assets
            SET width = COALESCE(?, width),
                height = COALESCE(?, height),
                orientation = COALESCE(?, orientation)
            WHERE id = ?
            """,
            (width, height, orientation, asset_id),
        )

    def update_effective_capture(
        self,
        asset_id: int,
        captured_at: str | None,
        captured_at_source: CapturedAtSource,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            "UPDATE assets SET captured_at = ?, captured_at_source = ? WHERE id = ?",
            (captured_at, captured_at_source.value, asset_id),
        )

    def set_favorite(
        self,
        asset_id: int,
        is_favorite: bool,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            "UPDATE assets SET is_favorite = ? WHERE id = ?",
            (1 if is_favorite else 0, asset_id),
        )

    def set_rejected(
        self,
        asset_id: int,
        is_rejected: bool,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            "UPDATE assets SET is_rejected = ? WHERE id = ?",
            (1 if is_rejected else 0, asset_id),
        )

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "assets")


class EventRepository(BaseRepository):
    def list_events(self) -> list[Event]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source_id, folder_id, title, start_at, end_at, inferred_place_name,
                       grouping_mode, user_locked, created_at, updated_at
                FROM events
                ORDER BY start_at, id
                """
            ).fetchall()
        return [_map_event(row) for row in rows]

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "events")


class TagRepository(BaseRepository):
    def list_tags(self) -> list[Tag]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, slug, category, color, description, created_at
                FROM tags
                ORDER BY category, name COLLATE NOCASE
                """
            ).fetchall()
        return [_map_tag(row) for row in rows]

    def get_by_id(self, tag_id: int, conn: sqlite3.Connection | None = None) -> Tag | None:
        if conn is None:
            with self.database.connect() as connection:
                return self.get_by_id(tag_id, connection)

        row = conn.execute(
            """
            SELECT id, name, slug, category, color, description, created_at
            FROM tags
            WHERE id = ?
            """,
            (tag_id,),
        ).fetchone()
        if row is None:
            return None
        return _map_tag(row)

    def get_or_create_tag(self, name: str, conn: sqlite3.Connection) -> Tag:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Nazev tagu nesmi byt prazdny.")

        existing = conn.execute(
            """
            SELECT id, name, slug, category, color, description, created_at
            FROM tags
            WHERE name = ?
            """,
            (normalized_name,),
        ).fetchone()
        if existing is not None:
            return _map_tag(existing)

        category = _extract_tag_category(normalized_name)
        slug = self._build_unique_slug(normalized_name, conn)
        cursor = conn.execute(
            "INSERT INTO tags (name, slug, category) VALUES (?, ?, ?)",
            (normalized_name, slug, category),
        )
        tag_id = int(cursor.lastrowid)
        created = self.get_by_id(tag_id, conn)
        if created is None:
            raise RepositoryError(f"Nepodarilo se nacist novy tag '{normalized_name}'.")
        return created

    def list_shortcut_bindings(
        self,
        scope: TagScope = TagScope.ASSET,
        conn: sqlite3.Connection | None = None,
    ) -> list[tuple[TagShortcut, Tag]]:
        if conn is None:
            with self.database.connect() as connection:
                return self.list_shortcut_bindings(scope, connection)

        rows = conn.execute(
            """
            SELECT
                s.id AS shortcut_id,
                s.key_sequence AS shortcut_key_sequence,
                s.scope AS shortcut_scope,
                s.created_at AS shortcut_created_at,
                t.id AS tag_id,
                t.name AS tag_name,
                t.slug AS tag_slug,
                t.category AS tag_category,
                t.color AS tag_color,
                t.description AS tag_description,
                t.created_at AS tag_created_at
            FROM tag_shortcuts s
            INNER JOIN tags t ON t.id = s.tag_id
            WHERE s.scope = ?
            ORDER BY s.key_sequence
            """,
            (scope.value,),
        ).fetchall()
        return [_map_shortcut_binding(row) for row in rows]

    def set_shortcut_binding(
        self,
        key_sequence: str,
        tag_id: int,
        scope: TagScope,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            """
            INSERT INTO tag_shortcuts (key_sequence, tag_id, scope)
            VALUES (?, ?, ?)
            ON CONFLICT(key_sequence) DO UPDATE SET
                tag_id = excluded.tag_id,
                scope = excluded.scope
            """,
            (key_sequence, tag_id, scope.value),
        )

    def delete_shortcut_binding(
        self,
        key_sequence: str,
        scope: TagScope,
        conn: sqlite3.Connection,
    ) -> None:
        conn.execute(
            "DELETE FROM tag_shortcuts WHERE key_sequence = ? AND scope = ?",
            (key_sequence, scope.value),
        )

    def list_direct_asset_tags(self, asset_id: int, conn: sqlite3.Connection | None = None) -> list[Tag]:
        if conn is None:
            with self.database.connect() as connection:
                return self.list_direct_asset_tags(asset_id, connection)

        rows = conn.execute(
            """
            SELECT t.id, t.name, t.slug, t.category, t.color, t.description, t.created_at
            FROM asset_tags at
            INNER JOIN tags t ON t.id = at.tag_id
            WHERE at.asset_id = ?
            ORDER BY t.category, t.name COLLATE NOCASE
            """,
            (asset_id,),
        ).fetchall()
        return [_map_tag(row) for row in rows]

    def list_folder_tags(self, folder_id: int, conn: sqlite3.Connection | None = None) -> list[Tag]:
        if conn is None:
            with self.database.connect() as connection:
                return self.list_folder_tags(folder_id, connection)

        rows = conn.execute(
            """
            SELECT t.id, t.name, t.slug, t.category, t.color, t.description, t.created_at
            FROM folder_tags ft
            INNER JOIN tags t ON t.id = ft.tag_id
            WHERE ft.folder_id = ?
            ORDER BY t.category, t.name COLLATE NOCASE
            """,
            (folder_id,),
        ).fetchall()
        return [_map_tag(row) for row in rows]

    def list_effective_asset_tags(
        self,
        asset_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[tuple[Tag, TagScope]]:
        if conn is None:
            with self.database.connect() as connection:
                return self.list_effective_asset_tags(asset_id, connection)

        rows = conn.execute(
            """
            SELECT t.id, t.name, t.slug, t.category, t.color, t.description, t.created_at, 'asset' AS tag_scope
            FROM asset_tags at
            INNER JOIN tags t ON t.id = at.tag_id
            WHERE at.asset_id = ?

            UNION ALL

            SELECT t.id, t.name, t.slug, t.category, t.color, t.description, t.created_at, 'folder' AS tag_scope
            FROM assets a
            INNER JOIN folder_tags ft ON ft.folder_id = a.folder_id
            INNER JOIN tags t ON t.id = ft.tag_id
            WHERE a.id = ?

            UNION ALL

            SELECT t.id, t.name, t.slug, t.category, t.color, t.description, t.created_at, 'event' AS tag_scope
            FROM assets a
            INNER JOIN event_tags et ON et.event_id = a.event_id
            INNER JOIN tags t ON t.id = et.tag_id
            WHERE a.id = ?

            ORDER BY tag_scope, name COLLATE NOCASE
            """,
            (asset_id, asset_id, asset_id),
        ).fetchall()
        return [(_map_tag(row), TagScope(str(row["tag_scope"]))) for row in rows]

    def set_asset_tag_assignment(
        self,
        asset_id: int,
        tag_id: int,
        is_assigned: bool,
        assigned_via: str,
        conn: sqlite3.Connection,
    ) -> None:
        if is_assigned:
            conn.execute(
                """
                INSERT INTO asset_tags (asset_id, tag_id, assigned_via)
                VALUES (?, ?, ?)
                ON CONFLICT(asset_id, tag_id) DO UPDATE SET
                    assigned_via = excluded.assigned_via,
                    assigned_at = CURRENT_TIMESTAMP
                """,
                (asset_id, tag_id, assigned_via),
            )
            return

        conn.execute(
            "DELETE FROM asset_tags WHERE asset_id = ? AND tag_id = ?",
            (asset_id, tag_id),
        )

    def set_folder_tag_assignment(
        self,
        folder_id: int,
        tag_id: int,
        is_assigned: bool,
        conn: sqlite3.Connection,
    ) -> None:
        if is_assigned:
            conn.execute(
                """
                INSERT INTO folder_tags (folder_id, tag_id)
                VALUES (?, ?)
                ON CONFLICT(folder_id, tag_id) DO UPDATE SET
                    assigned_at = CURRENT_TIMESTAMP
                """,
                (folder_id, tag_id),
            )
            return

        conn.execute(
            "DELETE FROM folder_tags WHERE folder_id = ? AND tag_id = ?",
            (folder_id, tag_id),
        )

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "tags")

    @staticmethod
    def _build_unique_slug(name: str, conn: sqlite3.Connection) -> str:
        base_slug = _slugify(name)
        slug = base_slug
        suffix = 2
        while conn.execute("SELECT 1 FROM tags WHERE slug = ?", (slug,)).fetchone() is not None:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        return slug


class AlbumRepository(BaseRepository):
    def list_albums(self) -> list[Album]:
        with self.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, album_type, description, sort_order, created_at, updated_at
                FROM albums
                ORDER BY updated_at DESC, name COLLATE NOCASE
                """
            ).fetchall()
        return [_map_album(row) for row in rows]

    def count(self) -> int:
        with self.database.connect() as conn:
            return self._count(conn, "albums")



def _asset_select_sql() -> str:
    return """
        SELECT
            id, source_id, folder_id, event_id, file_name, extension, relative_path, absolute_path,
            media_type, file_size, checksum_sha256, captured_at, captured_at_source, modified_at_fs,
            imported_at, width, height, orientation, rating, is_favorite, is_rejected
        FROM assets
    """



def _extract_tag_category(name: str) -> str | None:
    if ":" not in name:
        return None
    category, remainder = name.split(":", 1)
    category = category.strip()
    remainder = remainder.strip()
    if not category or not remainder:
        return None
    return category



def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "tag"



def _map_source(row: sqlite3.Row) -> Source:
    return Source(
        id=int(row["id"]),
        name=str(row["name"]),
        root_path=str(row["root_path"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )



def _map_folder(row: sqlite3.Row) -> Folder:
    return Folder(
        id=int(row["id"]),
        source_id=int(row["source_id"]),
        parent_id=row["parent_id"],
        relative_path=str(row["relative_path"]),
        absolute_path=str(row["absolute_path"]),
        folder_name=str(row["folder_name"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )



def _map_asset(row: sqlite3.Row) -> Asset:
    captured_at_source = row["captured_at_source"] or CapturedAtSource.UNKNOWN.value
    return Asset(
        id=int(row["id"]),
        source_id=int(row["source_id"]),
        folder_id=row["folder_id"],
        event_id=row["event_id"],
        file_name=str(row["file_name"]),
        extension=row["extension"],
        relative_path=str(row["relative_path"]),
        absolute_path=str(row["absolute_path"]),
        media_type=MediaType(str(row["media_type"])),
        file_size=row["file_size"],
        checksum_sha256=row["checksum_sha256"],
        captured_at=row["captured_at"],
        modified_at_fs=row["modified_at_fs"],
        imported_at=row["imported_at"],
        width=row["width"],
        height=row["height"],
        orientation=row["orientation"],
        rating=int(row["rating"]),
        is_favorite=bool(row["is_favorite"]),
        is_rejected=bool(row["is_rejected"]),
        captured_at_source=CapturedAtSource(str(captured_at_source)),
    )



def _map_event(row: sqlite3.Row) -> Event:
    return Event(
        id=int(row["id"]),
        source_id=int(row["source_id"]),
        folder_id=row["folder_id"],
        title=row["title"],
        start_at=row["start_at"],
        end_at=row["end_at"],
        inferred_place_name=row["inferred_place_name"],
        grouping_mode=GroupingMode(str(row["grouping_mode"])),
        user_locked=bool(row["user_locked"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )



def _map_tag(row: sqlite3.Row) -> Tag:
    return Tag(
        id=int(row["id"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        category=row["category"],
        color=row["color"],
        description=row["description"],
        created_at=row["created_at"],
    )



def _map_shortcut_binding(row: sqlite3.Row) -> tuple[TagShortcut, Tag]:
    shortcut = TagShortcut(
        id=int(row["shortcut_id"]),
        key_sequence=str(row["shortcut_key_sequence"]),
        tag_id=int(row["tag_id"]),
        scope=TagScope(str(row["shortcut_scope"])),
        created_at=row["shortcut_created_at"],
    )
    tag = Tag(
        id=int(row["tag_id"]),
        name=str(row["tag_name"]),
        slug=str(row["tag_slug"]),
        category=row["tag_category"],
        color=row["tag_color"],
        description=row["tag_description"],
        created_at=row["tag_created_at"],
    )
    return shortcut, tag



def _map_album(row: sqlite3.Row) -> Album:
    return Album(
        id=int(row["id"]),
        name=str(row["name"]),
        album_type=AlbumType(str(row["album_type"])),
        description=row["description"],
        sort_order=str(row["sort_order"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
