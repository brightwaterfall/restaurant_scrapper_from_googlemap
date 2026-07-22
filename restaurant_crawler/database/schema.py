"""SQLite schema definitions."""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS restaurants (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    country TEXT,
    latitude REAL,
    longitude REAL,
    google_maps_url TEXT,
    website TEXT,
    phone TEXT,
    email TEXT,
    facebook TEXT,
    instagram TEXT,
    delivery_platforms TEXT,
    categories TEXT,
    opening_hours TEXT,
    opening_hours_raw TEXT,
    currency TEXT DEFAULT 'BRL',
    normalized_name TEXT,
    normalized_address TEXT,
    fingerprint TEXT,
    status TEXT DEFAULT 'discovered',
    scrape_error TEXT,
    extra TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurants_fingerprint
    ON restaurants(fingerprint) WHERE fingerprint IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(normalized_name);
CREATE INDEX IF NOT EXISTS idx_restaurants_status ON restaurants(status);

CREATE TABLE IF NOT EXISTS menus (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL,
    title TEXT,
    source_url TEXT,
    source_type TEXT,
    local_path TEXT,
    currency TEXT DEFAULT 'BRL',
    item_count INTEGER DEFAULT 0,
    extracted INTEGER DEFAULT 0,
    extra TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_menus_restaurant ON menus(restaurant_id);

CREATE TABLE IF NOT EXISTS menu_items (
    id TEXT PRIMARY KEY,
    menu_id TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    category TEXT,
    name TEXT NOT NULL,
    description TEXT,
    price REAL,
    currency TEXT DEFAULT 'BRL',
    notes TEXT,
    availability TEXT,
    source_type TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (menu_id) REFERENCES menus(id) ON DELETE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_menu_items_menu ON menu_items(menu_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_restaurant ON menu_items(restaurant_id);

CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT,
    filename TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    content_type TEXT,
    is_thumbnail INTEGER DEFAULT 0,
    downloaded INTEGER DEFAULT 0,
    download_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_photos_restaurant ON photos(restaurant_id);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    discovered_at TEXT NOT NULL,
    raw_payload TEXT,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sources_restaurant ON sources(restaurant_id);

CREATE TABLE IF NOT EXISTS crawl_logs (
    id TEXT PRIMARY KEY,
    restaurant_id TEXT,
    level TEXT,
    event TEXT NOT NULL,
    message TEXT NOT NULL,
    url TEXT,
    details TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crawl_logs_created ON crawl_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_crawl_logs_event ON crawl_logs(event);

CREATE TABLE IF NOT EXISTS crawl_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
