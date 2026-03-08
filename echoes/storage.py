"""SQLite storage layer for journal entries."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from echoes.config import DB_PATH, DATA_DIR
from echoes.models import JournalEntry


# ── Schema ──────────────────────────────────────────────────────────
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    transcript      TEXT    NOT NULL,
    language        TEXT    DEFAULT 'unknown',
    mood_tag        TEXT    NOT NULL,
    confidence      REAL    DEFAULT 0.0,
    summary         TEXT    DEFAULT '',
    tags            TEXT    DEFAULT '',
    schema_version  INTEGER DEFAULT 1,
    audio_duration  REAL
);
"""


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating it if needed."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


# ── CRUD ────────────────────────────────────────────────────────────
def save_entry(entry: JournalEntry, db_path: Optional[Path] = None) -> int:
    """Insert a journal entry and return its row id."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO entries
                (timestamp, transcript, language, mood_tag, confidence,
                 summary, tags, schema_version, audio_duration)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.timestamp,
                entry.transcript,
                entry.language,
                entry.mood_tag,
                entry.confidence,
                entry.summary,
                entry.tags,
                entry.schema_version,
                entry.audio_duration,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]
    finally:
        conn.close()


def get_entries(
    limit: int = 20,
    offset: int = 0,
    db_path: Optional[Path] = None,
) -> list[JournalEntry]:
    """Fetch the most recent entries, newest first."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]
    finally:
        conn.close()


def get_mood_history(
    days: int = 30,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """Return mood tags and timestamps for the last N days."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            """
            SELECT timestamp, mood_tag, confidence
            FROM entries
            WHERE timestamp >= datetime('now', ?)
            ORDER BY timestamp ASC
            """,
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_entry_count(db_path: Optional[Path] = None) -> int:
    """Return total number of entries."""
    conn = _get_connection(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM entries").fetchone()
        return row["cnt"]
    finally:
        conn.close()


# ── Helpers ─────────────────────────────────────────────────────────
def _row_to_entry(row: sqlite3.Row) -> JournalEntry:
    return JournalEntry(
        id=row["id"],
        timestamp=row["timestamp"],
        transcript=row["transcript"],
        language=row["language"],
        mood_tag=row["mood_tag"],
        confidence=row["confidence"],
        summary=row["summary"],
        tags=row["tags"],
        schema_version=row["schema_version"],
        audio_duration=row["audio_duration"],
    )
