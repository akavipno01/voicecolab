from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "Voice Clone"
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("VOICE_CLONE_DATA_DIR", BASE_DIR / "data")).resolve()
VOICES_DIR = DATA_DIR / "voices"
OUTPUTS_DIR = DATA_DIR / "outputs"
TEMP_DIR = DATA_DIR / "temp"
MODELS_DIR = DATA_DIR / "models"
MODEL_DIR = MODELS_DIR / "omnivoice"
DB_PATH = DATA_DIR / "voice-clone.sqlite3"
MODEL_ID = os.environ.get("VOICE_CLONE_MODEL", "k2-fsa/OmniVoice")


def ensure_directories() -> None:
    for directory in (DATA_DIR, VOICES_DIR, OUTPUTS_DIR, TEMP_DIR, MODELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)
