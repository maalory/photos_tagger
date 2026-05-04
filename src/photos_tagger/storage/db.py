from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
import sqlite3

from photos_tagger.config import AppPaths, ensure_app_paths


class DatabaseManager:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    @property
    def schema_path(self) -> Path:
        return self.paths.project_root / "database" / "schema.sql"

    def initialize_schema(self) -> None:
        ensure_app_paths(self.paths)
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

        with sqlite3.connect(self.paths.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.executescript(self.schema_path.read_text(encoding="utf-8"))
            self._apply_compat_migrations(conn)
            conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        ensure_app_paths(self.paths)
        conn = sqlite3.connect(self.paths.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _apply_compat_migrations(self, conn: sqlite3.Connection) -> None:
        self._ensure_column(
            conn,
            table_name="assets",
            column_name="captured_at_source",
            column_sql="TEXT NOT NULL DEFAULT 'unknown'",
        )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_date_correction_batches_created_at ON date_correction_batches(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_asset_id ON asset_date_corrections(asset_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_batch_id ON asset_date_corrections(batch_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_is_active ON asset_date_corrections(is_active)"
        )

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_sql: str,
    ) -> None:
        existing_columns = {
            str(row[1])
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name in existing_columns:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")



def initialize_database(paths: AppPaths) -> None:
    DatabaseManager(paths).initialize_schema()



def get_connection(paths: AppPaths) -> sqlite3.Connection:
    return DatabaseManager(paths).get_connection()
