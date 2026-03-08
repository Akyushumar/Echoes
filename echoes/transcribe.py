"""Speech-to-text with triple provider fallback: Sarvam -> OpenAI API -> Local Whisper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import whisper
from openai import OpenAI
from sarvamai import SarvamAI

from echoes.config import OPENAI_API_KEY, SARVAM_API_KEY
from echoes.audio_utils import ensure_wav, get_audio_duration

logger = logging.getLogger(__name__)

# Cache the local model so it's only loaded once per process
_model_cache: dict[str, whisper.Whisper] = {}


def _get_local_model(model_name: str = "base") -> whisper.Whisper:
    """Load a local Whisper model, caching it for reuse."""
    if model_name not in _model_cache:
        _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


# ── Provider 1: Sarvam AI ──────────────────────────────────────────
def _transcribe_sarvam(wav_path: Path, language: Optional[str] = None) -> dict:
    """Transcribe using Sarvam AI (best for Indic languages)."""
    client = SarvamAI(api_subscription_key=SARVAM_API_KEY)

    with open(wav_path, "rb") as f:
        response = client.speech_to_text.transcribe(
            file=f,
            model="saaras:v3",
            mode="transcribe",
        )

    # Sarvam response has .transcript and .language_code
    transcript = getattr(response, "transcript", "") or ""
    lang_code = getattr(response, "language_code", "unknown") or "unknown"

    return {
        "transcript": transcript.strip(),
        "language": lang_code,
        "provider": "sarvam",
    }


# ── Provider 2: OpenAI Whisper API ─────────────────────────────────
def _transcribe_openai(wav_path: Path, language: Optional[str] = None) -> dict:
    """Transcribe using OpenAI Whisper API."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    with open(wav_path, "rb") as audio_file:
        kwargs = {
            "model": "whisper-1",
            "file": audio_file,
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language

        response = client.audio.transcriptions.create(**kwargs)

    detected_lang = getattr(response, "language", "unknown")
    return {
        "transcript": response.text.strip(),
        "language": detected_lang if detected_lang else "unknown",
        "provider": "openai_api",
    }


# ── Provider 3: Local Whisper ──────────────────────────────────────
def _transcribe_local(wav_path: Path, language: Optional[str] = None, model_name: str = "base") -> dict:
    """Transcribe using local Whisper model."""
    model = _get_local_model(model_name)
    options = {}
    if language:
        options["language"] = language

    result = model.transcribe(str(wav_path), **options)

    detected_lang = result.get("language", "unknown")
    transcript_text = result.get("text", "").strip()

    return {
        "transcript": transcript_text,
        "language": detected_lang if detected_lang else "unknown",
        "provider": "local_whisper",
    }


# ── Main Entry Point ──────────────────────────────────────────────
def transcribe_audio(
    filepath: str | Path,
    language: Optional[str] = None,
    model_name: str = "base",
) -> dict:
    """
    Transcribe an audio file with automatic fallback.

    Priority: Sarvam AI -> OpenAI API -> Local Whisper

    Args:
        filepath: Path to the audio file (any supported format).
        language: Optional ISO-639-1 language code hint.
        model_name: Whisper model size for local fallback.

    Returns:
        dict with keys: transcript, language, duration, provider
    """
    wav_path = ensure_wav(filepath)
    duration = get_audio_duration(filepath)

    # 1. Sarvam AI (primary — best for Indic languages)
    if SARVAM_API_KEY:
        try:
            result = _transcribe_sarvam(wav_path, language)
            result["duration"] = round(duration, 2)
            return result
        except Exception as e:
            logger.warning(f"Sarvam STT failed, trying next provider: {e}")

    # 2. OpenAI Whisper API
    if OPENAI_API_KEY:
        try:
            result = _transcribe_openai(wav_path, language)
            result["duration"] = round(duration, 2)
            return result
        except Exception as e:
            logger.warning(f"OpenAI API failed, falling back to local: {e}")

    # 3. Local Whisper (always available)
    result = _transcribe_local(wav_path, language, model_name)
    result["duration"] = round(duration, 2)
    return result
