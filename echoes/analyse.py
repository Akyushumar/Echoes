"""Emotion analysis using Google Gemini (google-genai SDK) with a fixed mood taxonomy."""

from __future__ import annotations

import json
import re

from google import genai
from google.genai.types import GenerateContentConfig

from echoes.config import GEMINI_API_KEY, MOOD_TAGS, MOOD_TAGS_STR, validate_keys
from echoes.models import MoodTag


# ── Prompt Template ─────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are an empathetic journaling assistant. Your job is to read a person's \
spoken journal transcript and produce:
1. A brief reflective summary (2-3 sentences) that mirrors the speaker's \
emotional state without being clinical.
2. A single mood tag from this exact list: {mood_tags}.
3. A confidence score between 0.0 and 1.0 for the mood tag.

Respond ONLY with valid JSON in this exact format (no markdown, no extra text):
{{"summary": "...", "mood_tag": "...", "confidence": 0.0}}
"""

_USER_PROMPT = """\
Here is the journal transcript to analyse:

\"\"\"{transcript}\"\"\"
"""


def analyse_emotion(transcript: str) -> dict:
    """
    Analyse the emotional tone of a journal transcript using Gemini.

    Args:
        transcript: The text transcript to analyse.

    Returns:
        dict with keys: summary, mood_tag, confidence
    """
    validate_keys(require_gemini=True)

    if not transcript.strip():
        return {
            "summary": "No content to analyse.",
            "mood_tag": "neutral",
            "confidence": 1.0,
        }

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=_USER_PROMPT.format(transcript=transcript),
        config=GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT.format(mood_tags=MOOD_TAGS_STR),
            temperature=0.1,
            max_output_tokens=300,
        ),
    )

    return _parse_response(response.text)


def _parse_response(raw: str) -> dict:
    """Parse Gemini's JSON response, with fallbacks for malformed output."""
    # Strip markdown fences if present
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "summary": raw.strip()[:200],
            "mood_tag": "neutral",
            "confidence": 0.0,
        }

    # Validate mood tag against taxonomy
    mood_raw = data.get("mood_tag", "neutral")
    mood = MoodTag.from_str(mood_raw)

    confidence = data.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence)))
    except (ValueError, TypeError):
        confidence = 0.0

    return {
        "summary": data.get("summary", ""),
        "mood_tag": mood.value,
        "confidence": confidence,
    }
