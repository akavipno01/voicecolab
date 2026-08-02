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

    DEFAULT_EN_REF_TEXT = (
        "They Laughed When She Bought a Flooded Orchard for $15 — Until Her Ducks Revealed What Lay Beneath"
    )

    DEFAULT_ZH_REF_TEXT = (
        "1979年己未属羊人2026年9月运势：苦尽甘来、破茧成蝶！财运与贵人运同时爆发！【命运解码】"
    )

    DEFAULT_JA_REF_TEXT = (
        "【癒しの声】「物語が映画のように見える人、見えない人の違い」についての動画をお届けいたします。"
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
        {"id": "sys_achernar_english", "name": "Achernar_English", "filename": "Achernar_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 65},
        {"id": "sys_achird_english", "name": "Achird_English", "filename": "Achird_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 66},
        {"id": "sys_algenib_english", "name": "Algenib_English", "filename": "Algenib_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 67},
        {"id": "sys_algieba_english", "name": "Algieba_English", "filename": "Algieba_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 68},
        {"id": "sys_alnilam_english", "name": "Alnilam_English", "filename": "Alnilam_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 69},
        {"id": "sys_aoede_english", "name": "Aoede_English", "filename": "Aoede_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 70},
        {"id": "sys_autonoe_english", "name": "Autonoe_English", "filename": "Autonoe_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 71},
        {"id": "sys_callirrhoe_english", "name": "Callirrhoe_English", "filename": "Callirrhoe_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 72},
        {"id": "sys_charon_english", "name": "Charon_English", "filename": "Charon_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 73},
        {"id": "sys_despina_english", "name": "Despina_English", "filename": "Despina_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 74},
        {"id": "sys_enceladus_english", "name": "Enceladus_English", "filename": "Enceladus_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 75},
        {"id": "sys_erinome_english", "name": "Erinome_English", "filename": "Erinome_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 76},
        {"id": "sys_fenrir_english", "name": "Fenrir_English", "filename": "Fenrir_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 77},
        {"id": "sys_gacrux_english", "name": "Gacrux_English", "filename": "Gacrux_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 78},
        {"id": "sys_iapetus_english", "name": "Iapetus_English", "filename": "Iapetus_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 79},
        {"id": "sys_kore_english", "name": "Kore_English", "filename": "Kore_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 80},
        {"id": "sys_laomedeia_english", "name": "Laomedeia_English", "filename": "Laomedeia_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 81},
        {"id": "sys_leda_english", "name": "Leda_English", "filename": "Leda_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 82},
        {"id": "sys_orus_english", "name": "Orus_English", "filename": "Orus_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 83},
        {"id": "sys_puck_english", "name": "Puck_English", "filename": "Puck_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 84},
        {"id": "sys_pulcherrima_english", "name": "Pulcherrima_English", "filename": "Pulcherrima_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 85},
        {"id": "sys_rasalgethi_english", "name": "Rasalgethi_English", "filename": "Rasalgethi_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 86},
        {"id": "sys_sadachbia_english", "name": "Sadachbia_English", "filename": "Sadachbia_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 87},
        {"id": "sys_sadaltager_english", "name": "Sadaltager_English", "filename": "Sadaltager_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 88},
        {"id": "sys_schedar_english", "name": "Schedar_English", "filename": "Schedar_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 89},
        {"id": "sys_sulafat_english", "name": "Sulafat_English", "filename": "Sulafat_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 90},
        {"id": "sys_umbriel_english", "name": "Umbriel_English", "filename": "Umbriel_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 91},
        {"id": "sys_vindemiatrix_english", "name": "Vindemiatrix_English", "filename": "Vindemiatrix_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 92},
        {"id": "sys_zephyr_english", "name": "Zephyr_English", "filename": "Zephyr_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 93},
        {"id": "sys_zubenelgenubi_english", "name": "Zubenelgenubi_English", "filename": "Zubenelgenubi_English.wav", "ref_text": DEFAULT_EN_REF_TEXT, "language": "en", "notes": "Giọng hệ thống", "created_offset": 94},
        {"id": "sys_achernar_chinese", "name": "Achernar_Chinese", "filename": "Achernar_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 95},
        {"id": "sys_achird_chinese", "name": "Achird_Chinese", "filename": "Achird_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 96},
        {"id": "sys_algenib_chinese", "name": "Algenib_Chinese", "filename": "Algenib_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 97},
        {"id": "sys_algieba_chinese", "name": "Algieba_Chinese", "filename": "Algieba_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 98},
        {"id": "sys_alnilam_chinese", "name": "Alnilam_Chinese", "filename": "Alnilam_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 99},
        {"id": "sys_aoede_chinese", "name": "Aoede_Chinese", "filename": "Aoede_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 100},
        {"id": "sys_autonoe_chinese", "name": "Autonoe_Chinese", "filename": "Autonoe_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 101},
        {"id": "sys_callirrhoe_chinese", "name": "Callirrhoe_Chinese", "filename": "Callirrhoe_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 102},
        {"id": "sys_charon_chinese", "name": "Charon_Chinese", "filename": "Charon_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 103},
        {"id": "sys_despina_chinese", "name": "Despina_Chinese", "filename": "Despina_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 104},
        {"id": "sys_enceladus_chinese", "name": "Enceladus_Chinese", "filename": "Enceladus_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 105},
        {"id": "sys_erinome_chinese", "name": "Erinome_Chinese", "filename": "Erinome_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 106},
        {"id": "sys_fenrir_chinese", "name": "Fenrir_Chinese", "filename": "Fenrir_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 107},
        {"id": "sys_gacrux_chinese", "name": "Gacrux_Chinese", "filename": "Gacrux_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 108},
        {"id": "sys_iapetus_chinese", "name": "Iapetus_Chinese", "filename": "Iapetus_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 109},
        {"id": "sys_kore_chinese", "name": "Kore_Chinese", "filename": "Kore_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 110},
        {"id": "sys_laomedeia_chinese", "name": "Laomedeia_Chinese", "filename": "Laomedeia_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 111},
        {"id": "sys_leda_chinese", "name": "Leda_Chinese", "filename": "Leda_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 112},
        {"id": "sys_orus_chinese", "name": "Orus_Chinese", "filename": "Orus_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 113},
        {"id": "sys_puck_chinese", "name": "Puck_Chinese", "filename": "Puck_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 114},
        {"id": "sys_pulcherrima_chinese", "name": "Pulcherrima_Chinese", "filename": "Pulcherrima_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 115},
        {"id": "sys_rasalgethi_chinese", "name": "Rasalgethi_Chinese", "filename": "Rasalgethi_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 116},
        {"id": "sys_sadachbia_chinese", "name": "Sadachbia_Chinese", "filename": "Sadachbia_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 117},
        {"id": "sys_sadaltager_chinese", "name": "Sadaltager_Chinese", "filename": "Sadaltager_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 118},
        {"id": "sys_schedar_chinese", "name": "Schedar_Chinese", "filename": "Schedar_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 119},
        {"id": "sys_sulafat_chinese", "name": "Sulafat_Chinese", "filename": "Sulafat_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 120},
        {"id": "sys_umbriel_chinese", "name": "Umbriel_Chinese", "filename": "Umbriel_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 121},
        {"id": "sys_vindemiatrix_chinese", "name": "Vindemiatrix_Chinese", "filename": "Vindemiatrix_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 122},
        {"id": "sys_zephyr_chinese", "name": "Zephyr_Chinese", "filename": "Zephyr_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 123},
        {"id": "sys_zubenelgenubi_chinese", "name": "Zubenelgenubi_Chinese", "filename": "Zubenelgenubi_Chinese.wav", "ref_text": DEFAULT_ZH_REF_TEXT, "language": "zh", "notes": "Giọng hệ thống", "created_offset": 124},
        {"id": "sys_achernar_japanese", "name": "Achernar_Japanese", "filename": "Achernar_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 125},
        {"id": "sys_achird_japanese", "name": "Achird_Japanese", "filename": "Achird_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 126},
        {"id": "sys_algenib_japanese", "name": "Algenib_Japanese", "filename": "Algenib_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 127},
        {"id": "sys_algieba_japanese", "name": "Algieba_Japanese", "filename": "Algieba_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 128},
        {"id": "sys_alnilam_japanese", "name": "Alnilam_Japanese", "filename": "Alnilam_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 129},
        {"id": "sys_aoede_japanese", "name": "Aoede_Japanese", "filename": "Aoede_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 130},
        {"id": "sys_autonoe_japanese", "name": "Autonoe_Japanese", "filename": "Autonoe_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 131},
        {"id": "sys_callirrhoe_japanese", "name": "Callirrhoe_Japanese", "filename": "Callirrhoe_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 132},
        {"id": "sys_charon_japanese", "name": "Charon_Japanese", "filename": "Charon_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 133},
        {"id": "sys_despina_japanese", "name": "Despina_Japanese", "filename": "Despina_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 134},
        {"id": "sys_enceladus_japanese", "name": "Enceladus_Japanese", "filename": "Enceladus_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 135},
        {"id": "sys_erinome_japanese", "name": "Erinome_Japanese", "filename": "Erinome_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 136},
        {"id": "sys_fenrir_japanese", "name": "Fenrir_Japanese", "filename": "Fenrir_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 137},
        {"id": "sys_gacrux_japanese", "name": "Gacrux_Japanese", "filename": "Gacrux_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 138},
        {"id": "sys_iapetus_japanese", "name": "Iapetus_Japanese", "filename": "Iapetus_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 139},
        {"id": "sys_kore_japanese", "name": "Kore_Japanese", "filename": "Kore_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 140},
        {"id": "sys_laomedeia_japanese", "name": "Laomedeia_Japanese", "filename": "Laomedeia_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 141},
        {"id": "sys_leda_japanese", "name": "Leda_Japanese", "filename": "Leda_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 142},
        {"id": "sys_orus_japanese", "name": "Orus_Japanese", "filename": "Orus_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 143},
        {"id": "sys_puck_japanese", "name": "Puck_Japanese", "filename": "Puck_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 144},
        {"id": "sys_pulcherrima_japanese", "name": "Pulcherrima_Japanese", "filename": "Pulcherrima_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 145},
        {"id": "sys_rasalgethi_japanese", "name": "Rasalgethi_Japanese", "filename": "Rasalgethi_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 146},
        {"id": "sys_sadachbia_japanese", "name": "Sadachbia_Japanese", "filename": "Sadachbia_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 147},
        {"id": "sys_sadaltager_japanese", "name": "Sadaltager_Japanese", "filename": "Sadaltager_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 148},
        {"id": "sys_schedar_japanese", "name": "Schedar_Japanese", "filename": "Schedar_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 149},
        {"id": "sys_sulafat_japanese", "name": "Sulafat_Japanese", "filename": "Sulafat_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 150},
        {"id": "sys_umbriel_japanese", "name": "Umbriel_Japanese", "filename": "Umbriel_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 151},
        {"id": "sys_vindemiatrix_japanese", "name": "Vindemiatrix_Japanese", "filename": "Vindemiatrix_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 152},
        {"id": "sys_zephyr_japanese", "name": "Zephyr_Japanese", "filename": "Zephyr_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 153},
        {"id": "sys_zubenelgenubi_japanese", "name": "Zubenelgenubi_Japanese", "filename": "Zubenelgenubi_Japanese.wav", "ref_text": DEFAULT_JA_REF_TEXT, "language": "jp", "notes": "Giọng hệ thống", "created_offset": 154},
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




