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
    
    DEFAULT_KO_REF_TEXT = (
        "오늘 영상은 1963년생 계묘생 토끼띠 전체에 해당하는 일반적인 운세입니다 "
        "태어난 시간과 사주에 따라 개개인의 운은 얼마든지 달라질 수 있으니 명리학적 참고용으로 활용해 주십시오"
    )

    DEFAULT_VI_REF_TEXT = (
        "Tử Vi Tuổi Nhâm Tý 1972 Tháng 7 Âm Lịch 2026: Biến Động Bất Ngờ Hay Đại Lộc Trời Cho?"
    )

    system_voices = [
        {"id": "sys_achernar", "name": "Achernar", "filename": "Achernar.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 5},
        {"id": "sys_achird", "name": "Achird", "filename": "Achird.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 6},
        {"id": "sys_algenib", "name": "Algenib", "filename": "Algenib.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 7},
        {"id": "sys_algieba", "name": "Algieba", "filename": "Algieba.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 8},
        {"id": "sys_alnilam", "name": "Alnilam", "filename": "Alnilam.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 9},
        {"id": "sys_aoede", "name": "Aoede", "filename": "Aoede.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 10},
        {"id": "sys_autonoe", "name": "Autonoe", "filename": "Autonoe.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 11},
        {"id": "sys_callirrhoe", "name": "Callirrhoe", "filename": "Callirrhoe.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 12},
        {"id": "sys_charon", "name": "Charon", "filename": "Charon.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 13},
        {"id": "sys_despina", "name": "Despina", "filename": "Despina.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 14},
        {"id": "sys_enceladus", "name": "Enceladus", "filename": "Enceladus.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 15},
        {"id": "sys_erinome", "name": "Erinome", "filename": "Erinome.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 16},
        {"id": "sys_fenrir", "name": "Fenrir", "filename": "Fenrir.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 17},
        {"id": "sys_gacrux", "name": "Gacrux", "filename": "Gacrux.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 18},
        {"id": "sys_iapetus", "name": "Iapetus", "filename": "Iapetus.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 19},
        {"id": "sys_kore", "name": "Kore", "filename": "Kore.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 20},
        {"id": "sys_laomedeia", "name": "Laomedeia", "filename": "Laomedeia.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 21},
        {"id": "sys_leda", "name": "Leda", "filename": "Leda.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 22},
        {"id": "sys_orus", "name": "Orus", "filename": "Orus.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 23},
        {"id": "sys_puck", "name": "Puck", "filename": "Puck.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 24},
        {"id": "sys_pulcherrima", "name": "Pulcherrima", "filename": "Pulcherrima.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 25},
        {"id": "sys_rasalgethi", "name": "Rasalgethi", "filename": "Rasalgethi.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 26},
        {"id": "sys_sadachbia", "name": "Sadachbia", "filename": "Sadachbia.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 27},
        {"id": "sys_sadaltager", "name": "Sadaltager", "filename": "Sadaltager.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 28},
        {"id": "sys_schedar", "name": "Schedar", "filename": "Schedar.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 29},
        {"id": "sys_sulafat", "name": "Sulafat", "filename": "Sulafat.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 30},
        {"id": "sys_umbriel", "name": "Umbriel", "filename": "Umbriel.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 31},
        {"id": "sys_vindemiatrix", "name": "Vindemiatrix", "filename": "Vindemiatrix.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 32},
        {"id": "sys_zephyr", "name": "Zephyr", "filename": "Zephyr.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 33},
        {"id": "sys_zubenelgenubi", "name": "Zubenelgenubi", "filename": "Zubenelgenubi.wav", "ref_text": DEFAULT_KO_REF_TEXT, "language": "ko", "notes": "Giọng hệ thống", "created_offset": 34},
        {"id": "sys_achernar_vietnam", "name": "Achernar_VietNam", "filename": "Achernar_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 35},
        {"id": "sys_achird_vietnam", "name": "Achird_VietNam", "filename": "Achird_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 36},
        {"id": "sys_algenib_vietnam", "name": "Algenib_VietNam", "filename": "Algenib_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 37},
        {"id": "sys_algieba_vietnam", "name": "Algieba_VietNam", "filename": "Algieba_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 38},
        {"id": "sys_alnilam_vietnam", "name": "Alnilam_VietNam", "filename": "Alnilam_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 39},
        {"id": "sys_aoede_vietnam", "name": "Aoede_VietNam", "filename": "Aoede_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 40},
        {"id": "sys_autonoe_vietnam", "name": "Autonoe_VietNam", "filename": "Autonoe_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 41},
        {"id": "sys_callirrhoe_vietnam", "name": "Callirrhoe_VietNam", "filename": "Callirrhoe_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 42},
        {"id": "sys_charon_vietnam", "name": "Charon_VietNam", "filename": "Charon_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 43},
        {"id": "sys_despina_vietnam", "name": "Despina_VietNam", "filename": "Despina_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 44},
        {"id": "sys_enceladus_vietnam", "name": "Enceladus_VietNam", "filename": "Enceladus_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 45},
        {"id": "sys_erinome_vietnam", "name": "Erinome_VietNam", "filename": "Erinome_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 46},
        {"id": "sys_fenrir_vietnam", "name": "Fenrir_VietNam", "filename": "Fenrir_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 47},
        {"id": "sys_gacrux_vietnam", "name": "Gacrux_VietNam", "filename": "Gacrux_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 48},
        {"id": "sys_iapetus_vietnam", "name": "Iapetus_VietNam", "filename": "Iapetus_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 49},
        {"id": "sys_kore_vietnam", "name": "Kore_VietNam", "filename": "Kore_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 50},
        {"id": "sys_laomedeia_vietnam", "name": "Laomedeia_VietNam", "filename": "Laomedeia_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 51},
        {"id": "sys_leda_vietnam", "name": "Leda_VietNam", "filename": "Leda_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 52},
        {"id": "sys_orus_vietnam", "name": "Orus_VietNam", "filename": "Orus_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 53},
        {"id": "sys_puck_vietnam", "name": "Puck_VietNam", "filename": "Puck_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 54},
        {"id": "sys_pulcherrima_vietnam", "name": "Pulcherrima_VietNam", "filename": "Pulcherrima_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 55},
        {"id": "sys_rasalgethi_vietnam", "name": "Rasalgethi_VietNam", "filename": "Rasalgethi_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 56},
        {"id": "sys_sadachbia_vietnam", "name": "Sadachbia_VietNam", "filename": "Sadachbia_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 57},
        {"id": "sys_sadaltager_vietnam", "name": "Sadaltager_VietNam", "filename": "Sadaltager_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 58},
        {"id": "sys_schedar_vietnam", "name": "Schedar_VietNam", "filename": "Schedar_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 59},
        {"id": "sys_sulafat_vietnam", "name": "Sulafat_VietNam", "filename": "Sulafat_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 60},
        {"id": "sys_umbriel_vietnam", "name": "Umbriel_VietNam", "filename": "Umbriel_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 61},
        {"id": "sys_vindemiatrix_vietnam", "name": "Vindemiatrix_VietNam", "filename": "Vindemiatrix_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 62},
        {"id": "sys_zephyr_vietnam", "name": "Zephyr_VietNam", "filename": "Zephyr_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 63},
        {"id": "sys_zubenelgenubi_vietnam", "name": "Zubenelgenubi_VietNam", "filename": "Zubenelgenubi_VietNam.wav", "ref_text": DEFAULT_VI_REF_TEXT, "language": "vi", "notes": "Giọng hệ thống", "created_offset": 64},
    ]

    # Ensure VOICES_DIR exists
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Use a fixed base timestamp so the system voices display in the correct order
    base_time = 1782163200.0
    
    with db() as connection:
        for v in system_voices:
            src_path = packaged_voices_dir / v["filename"]
            dst_path = VOICES_DIR / v["filename"]
            
            # Copy sample audio file to runtime voices directory if missing
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
                    (
                        v["id"],
                        v["name"],
                        v["filename"],
                        v.get("ref_text", ""),
                        v.get("language", "Vietnamese"),
                        v.get("notes", "Giọng hệ thống"),
                        created_at,
                        created_at,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE voice_profiles
                    SET ref_text = ?, language = ?, notes = ?
                    WHERE id = ? AND is_system = 1
                    """,
                    (
                        v.get("ref_text", ""),
                        v.get("language", "Vietnamese"),
                        v.get("notes", "Giọng hệ thống"),
                        v["id"],
                    ),
                )




