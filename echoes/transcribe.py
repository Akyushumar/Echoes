"""Speech-to-text using OpenAI Whisper (local, no API key required)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import whisper

from echoes.audio_utils import ensure_wav, get_audio_duration


# Cache the model so it's only loaded once per process
_model_cache: dict[str, whisper.Whisper] = {}


def _get_model(model_name: str = "base") -> whisper.Whisper:
    """Load a Whisper model, caching it for reuse."""
    if model_name not in _model_cache:
        _model_cache[model_name] = whisper.load_model(model_name)
    return _model_cache[model_name]


def transcribe_audio(
    filepath: str | Path,
    language: Optional[str] = None,
    model_name: str = "base",
) -> dict:
    """
    Transcribe an audio file using local Whisper.

    Args:
        filepath: Path to the audio file (any supported format).
        language: Optional ISO-639-1 language code to hint Whisper.
                  If None, Whisper auto-detects.
        model_name: Whisper model size. Options: tiny, base, small,
                    medium, large. Larger = more accurate but slower.

    Returns:
        dict with keys: transcript, language, duration
    """
    # Normalise audio to WAV
    wav_path = ensure_wav(filepath)
    duration = get_audio_duration(filepath)

    # Verify WAV file
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        raise RuntimeError(f"Failed to generate a valid WAV file for transcription: {wav_path}")

    model = _get_model(model_name)

    # Build transcription options
    options = {}
    if language:
        options["language"] = language

    try:
        result = model.transcribe(str(wav_path), **options)
        detected_lang = result.get("language", "unknown")
        transcript_text = result.get("text", "").strip()
    finally:
        # Clean up temp file
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "transcript": transcript_text,
        "language": detected_lang if detected_lang else "unknown",
        "duration": round(duration, 2),
    }
