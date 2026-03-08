"""Data models for Echoes journal entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class MoodTag(str, Enum):
    """Fixed mood taxonomy — every journal entry gets one of these."""
    HAPPY = "happy"
    EXCITED = "excited"
    GRATEFUL = "grateful"
    CALM = "calm"
    REFLECTIVE = "reflective"
    HOPEFUL = "hopeful"
    NEUTRAL = "neutral"
    ANXIOUS = "anxious"
    FRUSTRATED = "frustrated"
    SAD = "sad"

    @classmethod
    def from_str(cls, value: str) -> MoodTag:
        """Parse a string into a MoodTag, defaulting to NEUTRAL if unrecognised."""
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.NEUTRAL


@dataclass
class JournalEntry:
    """A single journal entry produced by the Echoes pipeline."""
    id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    transcript: str = ""
    language: str = "unknown"
    mood_tag: str = "neutral"
    confidence: float = 0.0
    summary: str = ""
    tags: str = ""                  # comma-separated user tags
    schema_version: int = 1
    audio_duration: Optional[float] = None
