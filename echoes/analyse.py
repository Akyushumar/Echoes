"""Emotion analysis with triple fallback: Gemini -> Sarvam Chat -> Local keyword classifier."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

from echoes.config import GEMINI_API_KEY, SARVAM_API_KEY, MOOD_TAGS, MOOD_TAGS_STR
from echoes.models import MoodTag

logger = logging.getLogger(__name__)

# ── Shared Prompt ──────────────────────────────────────────────────
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


# ── Provider 1: Gemini (with retry) ───────────────────────────────
def _analyse_gemini(transcript: str) -> dict:
    """Analyse emotion with Gemini 2.0 Flash + exponential backoff."""
    from google import genai
    from google.genai.types import GenerateContentConfig

    client = genai.Client(api_key=GEMINI_API_KEY)

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=_USER_PROMPT.format(transcript=transcript),
                config=GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT.format(mood_tags=MOOD_TAGS_STR),
                    temperature=0.1,
                    max_output_tokens=300,
                ),
            )
            result = _parse_json_response(response.text)
            result["provider"] = "gemini"
            return result

        except Exception as e:
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(
                f"Gemini attempt {attempt + 1}/3 failed: {e}. "
                f"Retrying in {wait}s..."
            )
            if attempt < 2:
                time.sleep(wait)
            else:
                raise  # Let caller handle after all retries exhausted


# ── Provider 2: Sarvam Chat ───────────────────────────────────────
def _analyse_sarvam(transcript: str) -> dict:
    """Analyse emotion via Sarvam AI's chat completions endpoint."""
    from sarvamai import SarvamAI

    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    response = client.chat.completions(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT.format(mood_tags=MOOD_TAGS_STR)},
            {"role": "user", "content": _USER_PROMPT.format(transcript=transcript)},
        ],
        model="sarvam-m",
        max_tokens=300,
        temperature=0.1,
    )

    # Extract text from Sarvam response
    raw_text = ""
    if hasattr(response, "choices") and response.choices:
        choice = response.choices[0]
        if hasattr(choice, "message") and hasattr(choice.message, "content"):
            raw_text = choice.message.content
    elif hasattr(response, "text"):
        raw_text = response.text
    else:
        raw_text = str(response)

    result = _parse_json_response(raw_text)
    result["provider"] = "sarvam"
    return result


# ── Provider 3: Local Keyword Classifier ──────────────────────────
# Curated word lists for each mood — covers English + common Hinglish
_MOOD_KEYWORDS: dict[str, list[str]] = {
    "happy": [
        "happy", "joy", "joyful", "glad", "cheerful", "delighted", "wonderful",
        "great", "amazing", "love", "loving", "smile", "laugh", "fun", "enjoy",
        "pleased", "content", "blessed", "khush", "maza", "anand", "pyar",
    ],
    "excited": [
        "excited", "thrilled", "awesome", "incredible", "fantastic", "pumped",
        "energized", "can't wait", "stoked", "wow", "unbelievable", "fired up",
        "eager", "anticipation", "josh", "dhoom",
    ],
    "grateful": [
        "grateful", "thankful", "appreciate", "blessed", "fortunate", "lucky",
        "thanks", "gratitude", "thank god", "shukar", "dhanyavaad", "kripa",
    ],
    "calm": [
        "calm", "peaceful", "serene", "relaxed", "tranquil", "quiet", "still",
        "at ease", "comfortable", "soothing", "gentle", "rest", "shanti",
        "sukoon", "chain",
    ],
    "reflective": [
        "think", "thinking", "reflect", "wonder", "ponder", "remember",
        "looking back", "realise", "realize", "notice", "observe", "consider",
        "perhaps", "maybe", "memories", "sochta", "yaad",
    ],
    "hopeful": [
        "hope", "hopeful", "optimistic", "future", "forward", "better",
        "improve", "believe", "faith", "trust", "positive", "looking ahead",
        "bright", "possible", "asha", "umeed", "vishwas",
    ],
    "neutral": [
        "okay", "fine", "alright", "normal", "usual", "regular", "nothing",
        "just", "routine", "theek",
    ],
    "anxious": [
        "anxious", "worried", "nervous", "stress", "stressed", "tense",
        "afraid", "fear", "scared", "panic", "uneasy", "restless", "concern",
        "overthink", "tension", "dar", "chinta", "pareshan",
    ],
    "frustrated": [
        "frustrated", "angry", "annoyed", "irritated", "upset", "mad",
        "furious", "rage", "hate", "sick of", "tired of", "fed up",
        "unfair", "disgusted", "stupid", "gussa", "naraz",
    ],
    "sad": [
        "sad", "unhappy", "depressed", "down", "lonely", "alone", "cry",
        "tears", "heartbreak", "grief", "loss", "miss", "missing", "sorrow",
        "hurt", "pain", "dukh", "udas", "rona", "tanha",
    ],
}


def _analyse_local(transcript: str) -> dict:
    """Score transcript against keyword lists for each mood."""
    text = transcript.lower()

    scores: dict[str, float] = {}
    for mood, keywords in _MOOD_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            # Count occurrences (weighted by keyword length for specificity)
            count = text.count(kw)
            if count > 0:
                weight = len(kw.split()) * 0.5 + 0.5  # multi-word = higher weight
                score += count * weight
        scores[mood] = score

    total = sum(scores.values())
    if total == 0:
        return {
            "summary": "Could not determine specific emotion from the text.",
            "mood_tag": "neutral",
            "confidence": 0.3,
            "provider": "local",
        }

    # Pick the top mood
    top_mood = max(scores, key=scores.get)
    confidence = min(0.85, scores[top_mood] / max(total, 1) * 1.2)

    # Generate a simple summary
    summary = _generate_local_summary(top_mood, transcript)

    return {
        "summary": summary,
        "mood_tag": top_mood,
        "confidence": round(confidence, 2),
        "provider": "local",
    }


def _generate_local_summary(mood: str, transcript: str) -> str:
    """Generate a simple reflective summary based on mood."""
    templates = {
        "happy": "The speaker expresses positive feelings and a sense of joy.",
        "excited": "The speaker shows high energy and enthusiasm about something.",
        "grateful": "The speaker reflects on things they appreciate and feel thankful for.",
        "calm": "The speaker seems at peace and in a relaxed state of mind.",
        "reflective": "The speaker is looking back on experiences and contemplating their thoughts.",
        "hopeful": "The speaker expresses optimism about what lies ahead.",
        "neutral": "The speaker shares their thoughts in a matter-of-fact tone.",
        "anxious": "The speaker seems to be dealing with worry or nervousness.",
        "frustrated": "The speaker expresses dissatisfaction or irritation about a situation.",
        "sad": "The speaker conveys feelings of sadness or emotional pain.",
    }
    preview = transcript[:100].strip()
    base = templates.get(mood, "The speaker shares their thoughts.")
    return f"{base} They mention: \"{preview}...\""


# ── JSON Parser (shared) ──────────────────────────────────────────
def _parse_json_response(raw: str) -> dict:
    """Parse JSON response from LLM, with fallbacks for malformed output."""
    # Strip markdown fences
    cleaned = re.sub(r"```json\s*", "", raw)
    cleaned = re.sub(r"```\s*", "", cleaned)
    # Strip <think>...</think> blocks (Sarvam's chain-of-thought)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    # Try direct JSON parse
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract JSON object from mixed text
        match = re.search(r'\{[^{}]*"mood_tag"[^{}]*\}', cleaned)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                return {
                    "summary": raw.strip()[:200],
                    "mood_tag": "neutral",
                    "confidence": 0.0,
                }
        else:
            return {
                "summary": raw.strip()[:200],
                "mood_tag": "neutral",
                "confidence": 0.0,
            }

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


# ── Main Entry Point ──────────────────────────────────────────────
def analyse_emotion(transcript: str) -> dict:
    """
    Analyse emotional tone with automatic fallback.

    Priority: Gemini (with retry) -> Sarvam Chat -> Local keyword classifier

    Args:
        transcript: The text transcript to analyse.

    Returns:
        dict with keys: summary, mood_tag, confidence, provider
    """
    if not transcript.strip():
        return {
            "summary": "No content to analyse.",
            "mood_tag": "neutral",
            "confidence": 1.0,
            "provider": "none",
        }

    # 1. Gemini (primary)
    if GEMINI_API_KEY:
        try:
            return _analyse_gemini(transcript)
        except Exception as e:
            logger.warning(f"Gemini analysis failed after retries: {e}")

    # 2. Sarvam Chat (fallback)
    if SARVAM_API_KEY:
        try:
            return _analyse_sarvam(transcript)
        except Exception as e:
            logger.warning(f"Sarvam analysis failed: {e}")

    # 3. Local keyword classifier (always available)
    return _analyse_local(transcript)
