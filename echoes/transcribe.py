"""Speech-to-text using OpenAI Whisper (API first, Local fallback)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import whisper
from openai import OpenAI

from echoes.config import OPENAI_API_KEY, validate_keys
from echoes.audio_utils import ensure_wav, get_audio_duration

# Cache the local model so it's only loaded once per process
_model_cache: dict[str, whisper.Whisper] = {}


def _get_local_model(model_name: str = "base") -> whisper.Whisper:
    """Load a local Whisper model, caching it for reuse."""
    if model_name not in _model_cache:
        _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


def transcribe_audio(
    filepath: str | Path,
    language: Optional[str] = None,
    model_name: str = "base",
) -> dict:
    """
    Transcribe an audio file. 
    Tries OpenAI API first if OPENAI_API_KEY is present, 
    otherwise falls back to local Whisper.

    Args:
        filepath: Path to the audio file (any supported format).
        language: Optional ISO-639-1 language code.
        model_name: Whisper model size for local fallback (tiny, base, etc.).

    Returns:
        dict with keys: transcript, language, duration, provider
    """
    # Normalise audio to WAV
    wav_path = ensure_wav(filepath)
    duration = get_audio_duration(filepath)

    # 1. Try OpenAI API if key is available
    if OPENAI_API_KEY:
        try:
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
                "duration": round(duration, 2),
                "provider": "openai_api",
            }
        except Exception as e:
            # Log failure but proceed to local fallback
            logging.warning(f"OpenAI API transcription failed, falling back to local: {e}")

    # 2. Local Fallback
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
        "duration": round(duration, 2),
        "provider": "local_whisper",
    }
