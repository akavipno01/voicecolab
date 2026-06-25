from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from .config import DB_PATH, ensure_directories, VOICES_DIR


SCHEMA = """
CREATE TABLE IF NOT EXISTS voice_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ref_audio_path TEXT NOT NULL,
    ref_text TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT 'Auto',
    notes TEXT NOT NULL DEFAULT '',
    consent_confirmed INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    is_system INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    profile_id TEXT,
    profile_name TEXT NOT NULL,
    text TEXT NOT NULL,
    language TEXT NOT NULL,
    audio_path TEXT NOT NULL,
    output_format TEXT NOT NULL DEFAULT 'wav',
    duration_seconds REAL NOT NULL,
    generation_time REAL NOT NULL,
    seed INTEGER NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES voice_profiles(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_created ON voice_profiles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_generations_created ON generations(created_at DESC);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    ensure_directories()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def db():
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with db() as connection:
        connection.executescript(SCHEMA)
        
        # Generations table migration
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(generations)").fetchall()
        }
        if "output_format" not in columns:
            connection.execute(
                "ALTER TABLE generations "
                "ADD COLUMN output_format TEXT NOT NULL DEFAULT 'wav'"
            )
            
        # Voice profiles table migration for is_system
        columns_profiles = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(voice_profiles)").fetchall()
        }
        if "is_system" not in columns_profiles:
            connection.execute(
                "ALTER TABLE voice_profiles "
                "ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0"
            )
            
    # Copy sample WAV files and seed system voice profiles
    initialize_system_voices()


def initialize_system_voices() -> None:
    from pathlib import Path
    import shutil
    
    # Path to packaged voices
    packaged_voices_dir = Path(__file__).resolve().parent / "voices"
    system_voices = [
        {"id": "sys_tutrinh", "name": "Tú Trinh", "filename": "tutrinh.wav", "created_offset": 0},
        {"id": "sys_saigon1", "name": "Sài Gòn 1", "filename": "saigon1.wav", "created_offset": 1},
        {"id": "sys_saigon2", "name": "Sài Gòn 2", "filename": "saigon2.wav", "created_offset": 2},
        {"id": "sys_saigon3", "name": "Sài Gòn 3", "filename": "saigon3.wav", "created_offset": 3},
        {"id": "sys_saigon4", "name": "Sài Gòn 4", "filename": "saigon4.wav", "created_offset": 4},
    ]
    
    # Ensure VOICES_DIR exists
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use a fixed base timestamp so the system voices display in the correct order
    # (Tú Trinh has lowest, Saigon 4 has highest, so Saigon 4 is first when sorted by created_at DESC)
    base_time = 1782163200.0
    
    with db() as connection:
        for v in system_voices:
            src_path = packaged_voices_dir / v["filename"]
            dst_path = VOICES_DIR / v["filename"]
            
            # Copy sample WAV file to runtime voices directory if missing
            if src_path.exists() and not dst_path.exists():
                try:
                    shutil.copy2(src_path, dst_path)
                except Exception as e:
                    print(f"Error copying system voice file {v['filename']}: {e}")
                    
            # Check if database entry already exists
            row = connection.execute(
                "SELECT id FROM voice_profiles WHERE id = ?", (v["id"],)
            ).fetchone()
            
            if not row:
                created_at = base_time + v["created_offset"]
                connection.execute(
                    """
                    INSERT INTO voice_profiles (
                        id, name, ref_audio_path, ref_text, language, notes,
                        consent_confirmed, created_at, updated_at, is_system
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, 1)
                    """,
                    (v["id"], v["name"], v["filename"], "", "Vietnamese", "Giọng hệ thống", created_at, created_at)
                )

