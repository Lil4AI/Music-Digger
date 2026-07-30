-- EDMサブジャンル自動判定システム — DBスキーマ定義
-- このファイルが正 (CONTRACTS.md のスキーマはここの要約)

CREATE TABLE IF NOT EXISTS tracks (
    track_id              TEXT PRIMARY KEY,
    source                TEXT,
    source_url            TEXT UNIQUE,
    title                 TEXT,
    artist                TEXT,
    raw_audio_path        TEXT,
    drop_start_sec        REAL,
    drop_end_sec          REAL,
    separated_at          TIMESTAMP,
    features_extracted_at TIMESTAMP,
    classified_at         TIMESTAMP,
    apple_music_id        TEXT,
    identified_at         TIMESTAMP,
    sync_status           TEXT,
    synced_at             TIMESTAMP,
    status                TEXT,
    ai_label              TEXT,
    ai_confidence         REAL,
    human_label           TEXT,
    created_at            TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genre_probabilities (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id       TEXT REFERENCES tracks(track_id),
    genre_label    TEXT,
    probability    REAL,
    model_version  TEXT,
    created_at     TIMESTAMP
);
