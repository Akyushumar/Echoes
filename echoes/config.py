"""Configuration, API key validation, and shared constants."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv


# ── Load environment ────────────────────────────────────────────────
# Walk up from this file to find .env at project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


# ── API Keys ────────────────────────────────────────────────────────
OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
SARVAM_API_KEY: str | None = os.getenv("SARVAM_API_KEY")  # reserved for Phase 2


# ── Mood Taxonomy ───────────────────────────────────────────────────
MOOD_TAGS = [
    "happy",
    "excited",
    "grateful",
    "calm",
    "reflective",
    "hopeful",
    "neutral",
    "anxious",
    "frustrated",
    "sad",
]

MOOD_TAGS_STR = ", ".join(MOOD_TAGS)   # for prompt injection


# ── Paths ───────────────────────────────────────────────────────────
DATA_DIR = _project_root / "data"
DB_PATH = DATA_DIR / "echoes.db"


# ── Validation ──────────────────────────────────────────────────────
def validate_keys(require_openai: bool = False, require_gemini: bool = True) -> None:
    """Check that required API keys are present. Exit with a clear message if not."""
    missing = []
    if require_openai and not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if require_gemini and not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")

    if missing:
        print(f"❌ Missing API key(s) in .env: {', '.join(missing)}")
        print(f"   Expected .env location: {_project_root / '.env'}")
        sys.exit(1)
