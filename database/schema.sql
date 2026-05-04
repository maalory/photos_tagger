PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    parent_id INTEGER,
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL UNIQUE,
    folder_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES folders(id) ON DELETE CASCADE,
    UNIQUE (source_id, relative_path)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    folder_id INTEGER,
    title TEXT,
    start_at TEXT,
    end_at TEXT,
    inferred_place_name TEXT,
    grouping_mode TEXT NOT NULL DEFAULT 'auto' CHECK (grouping_mode IN ('auto', 'manual')),
    user_locked INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL,
    folder_id INTEGER,
    event_id INTEGER,
    file_name TEXT NOT NULL,
    extension TEXT,
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL UNIQUE,
    media_type TEXT NOT NULL DEFAULT 'photo' CHECK (media_type IN ('photo', 'video')),
    file_size INTEGER,
    checksum_sha256 TEXT,
    captured_at TEXT,
    captured_at_source TEXT NOT NULL DEFAULT 'unknown' CHECK (captured_at_source IN ('exif', 'filesystem', 'manual', 'derived', 'unknown')),
    modified_at_fs TEXT,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    width INTEGER,
    height INTEGER,
    orientation INTEGER,
    rating INTEGER NOT NULL DEFAULT 0 CHECK (rating BETWEEN 0 AND 5),
    is_favorite INTEGER NOT NULL DEFAULT 0,
    is_rejected INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE SET NULL,
    UNIQUE (source_id, relative_path)
);

CREATE TABLE IF NOT EXISTS places (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'offline',
    country_code TEXT,
    country_name TEXT,
    region_name TEXT,
    city_name TEXT,
    locality_name TEXT,
    latitude REAL,
    longitude REAL,
    geohash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset_metadata (
    asset_id INTEGER PRIMARY KEY,
    taken_at_original TEXT,
    timezone_offset TEXT,
    gps_lat REAL,
    gps_lng REAL,
    gps_alt REAL,
    camera_make TEXT,
    camera_model TEXT,
    lens_model TEXT,
    exif_json TEXT,
    place_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (place_id) REFERENCES places(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS date_correction_batches (
    id INTEGER PRIMARY KEY,
    operation_type TEXT NOT NULL CHECK (operation_type IN ('set', 'shift', 'timezone', 'clear')),
    target_scope TEXT NOT NULL CHECK (target_scope IN ('asset', 'folder', 'event', 'selection', 'filter')),
    target_selector_json TEXT,
    parameters_json TEXT NOT NULL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset_date_corrections (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    batch_id INTEGER,
    correction_mode TEXT NOT NULL CHECK (correction_mode IN ('set', 'shift', 'timezone', 'clear')),
    manual_captured_at TEXT,
    shift_minutes INTEGER,
    timezone_offset_override TEXT,
    previous_captured_at TEXT,
    new_captured_at TEXT,
    previous_source TEXT CHECK (previous_source IN ('exif', 'filesystem', 'manual', 'derived', 'unknown')),
    new_source TEXT NOT NULL CHECK (new_source IN ('exif', 'filesystem', 'manual', 'derived', 'unknown')),
    note TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (batch_id) REFERENCES date_correction_batches(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    category TEXT,
    color TEXT,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tag_shortcuts (
    id INTEGER PRIMARY KEY,
    key_sequence TEXT NOT NULL UNIQUE,
    tag_id INTEGER NOT NULL,
    scope TEXT NOT NULL DEFAULT 'asset' CHECK (scope IN ('asset', 'folder', 'event', 'selection')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS asset_tags (
    asset_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    assigned_via TEXT NOT NULL DEFAULT 'manual' CHECK (assigned_via IN ('manual', 'shortcut', 'bulk', 'import')),
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, tag_id),
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS folder_tags (
    folder_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (folder_id, tag_id),
    FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS event_tags (
    event_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    assigned_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    album_type TEXT NOT NULL DEFAULT 'static' CHECK (album_type IN ('static', 'smart', 'event')),
    description TEXT,
    sort_order TEXT NOT NULL DEFAULT 'captured_at_desc',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS album_items (
    album_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,
    position INTEGER,
    added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (album_id, asset_id),
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS album_rules (
    id INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL,
    rule_json TEXT NOT NULL,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (album_id) REFERENCES albums(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS thumbnails (
    asset_id INTEGER PRIMARY KEY,
    cache_key TEXT NOT NULL UNIQUE,
    relative_path TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_folders_source_id ON folders(source_id);
CREATE INDEX IF NOT EXISTS idx_folders_parent_id ON folders(parent_id);
CREATE INDEX IF NOT EXISTS idx_events_source_id ON events(source_id);
CREATE INDEX IF NOT EXISTS idx_events_folder_id ON events(folder_id);
CREATE INDEX IF NOT EXISTS idx_assets_source_id ON assets(source_id);
CREATE INDEX IF NOT EXISTS idx_assets_folder_id ON assets(folder_id);
CREATE INDEX IF NOT EXISTS idx_assets_event_id ON assets(event_id);
CREATE INDEX IF NOT EXISTS idx_assets_captured_at ON assets(captured_at);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_place_id ON asset_metadata(place_id);
CREATE INDEX IF NOT EXISTS idx_date_correction_batches_created_at ON date_correction_batches(created_at);
CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_asset_id ON asset_date_corrections(asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_batch_id ON asset_date_corrections(batch_id);
CREATE INDEX IF NOT EXISTS idx_asset_date_corrections_is_active ON asset_date_corrections(is_active);
CREATE INDEX IF NOT EXISTS idx_asset_tags_tag_id ON asset_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_folder_tags_tag_id ON folder_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_event_tags_tag_id ON event_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_albums_type ON albums(album_type);
