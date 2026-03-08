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
    audio_duration  REAL,
    audio_path      TEXT    DEFAULT ''
);
"""

_MIGRATE_ADD_AUDIO_PATH = """
ALTER TABLE entries ADD COLUMN audio_path TEXT DEFAULT '';
"""


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database, creating it if needed."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_TABLE)
    conn.commit()
    # Migrate: add audio_path if missing (for existing databases)
    try:
        conn.execute(_MIGRATE_ADD_AUDIO_PATH)
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
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
                 summary, tags, schema_version, audio_duration, audio_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                entry.audio_path or "",
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


def search_entries(
    keyword: Optional[str] = None,
    mood_tag: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> list[JournalEntry]:
    """Search entries by keyword, mood, and/or date range."""
    conn = _get_connection(db_path)
    try:
        clauses = []
        params: list = []

        if keyword:
            clauses.append("(transcript LIKE ? OR summary LIKE ? OR tags LIKE ?)")
            kw = f"%{keyword}%"
            params.extend([kw, kw, kw])

        if mood_tag:
            clauses.append("mood_tag = ?")
            params.append(mood_tag.lower())

        if date_from:
            clauses.append("timestamp >= ?")
            params.append(date_from)

        if date_to:
            clauses.append("timestamp <= ?")
            params.append(date_to)

        where = " AND ".join(clauses) if clauses else "1=1"
        query = f"SELECT * FROM entries WHERE {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [_row_to_entry(r) for r in rows]
    finally:
        conn.close()


def get_all_entries(db_path: Optional[Path] = None) -> list[JournalEntry]:
    """Fetch all entries (for export). Oldest first."""
    conn = _get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM entries ORDER BY timestamp ASC"
        ).fetchall()
        return [_row_to_entry(r) for r in rows]
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
        audio_path=row["audio_path"] if "audio_path" in row.keys() else "",
    )
