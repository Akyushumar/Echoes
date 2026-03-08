"""Speech-to-text with triple provider fallback: Sarvam -> OpenAI API -> Local Whisper.

Audio is preprocessed before transcription:
1. Speed up by 1.25x to fit more words per chunk
2. Split into 29.99s fragments (Sarvam's 30s limit)
3. Transcribe each chunk and stitch results together
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import whisper
from openai import OpenAI
from sarvamai import SarvamAI

from echoes.config import OPENAI_API_KEY, SARVAM_API_KEY
from echoes.audio_utils import ensure_wav, get_audio_duration, speedup_audio, chunk_audio

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


# ── Single chunk transcription with fallback ──────────────────────
def _transcribe_chunk(wav_path: Path, language: Optional[str], model_name: str) -> dict:
    """Transcribe a single audio chunk with provider fallback."""

    # 1. Sarvam AI
    if SARVAM_API_KEY:
        try:
            return _transcribe_sarvam(wav_path, language)
        except Exception as e:
            logger.warning(f"Sarvam STT failed on chunk, trying next: {e}")

    # 2. OpenAI Whisper API
    if OPENAI_API_KEY:
        try:
            return _transcribe_openai(wav_path, language)
        except Exception as e:
            logger.warning(f"OpenAI API failed on chunk, falling back to local: {e}")

    # 3. Local Whisper
    return _transcribe_local(wav_path, language, model_name)


# ── Main Entry Point ──────────────────────────────────────────────
def transcribe_audio(
    filepath: str | Path,
    language: Optional[str] = None,
    model_name: str = "base",
    speed_factor: float = 1.25,
) -> dict:
    """
    Transcribe an audio file with preprocessing and automatic fallback.

    Pipeline:
      1. Convert to WAV
      2. Speed up by speed_factor (default 1.25x)
      3. Split into 29.99s chunks
      4. Transcribe each chunk (Sarvam -> OpenAI -> Local)
      5. Stitch transcripts together

    Args:
        filepath: Path to the audio file (any supported format).
        language: Optional ISO-639-1 language code hint.
        model_name: Whisper model size for local fallback.
        speed_factor: Audio speedup factor (1.0 = no change).

    Returns:
        dict with keys: transcript, language, duration, provider
    """
    wav_path = ensure_wav(filepath)
    duration = get_audio_duration(filepath)

    # Step 1: Speed up
    if speed_factor > 1.0:
        wav_path = speedup_audio(wav_path, factor=speed_factor)

    # Step 2: Chunk into 29.99s fragments
    chunks = chunk_audio(wav_path, chunk_ms=29_990)

    # Step 3: Transcribe each chunk
    transcripts: list[str] = []
    detected_lang = "unknown"
    provider_used = "unknown"

    for i, chunk_path in enumerate(chunks):
        result = _transcribe_chunk(chunk_path, language, model_name)
        transcripts.append(result["transcript"])
        if i == 0:
            detected_lang = result["language"]
            provider_used = result["provider"]

    # Step 4: Stitch
    full_transcript = " ".join(t for t in transcripts if t)

    return {
        "transcript": full_transcript,
        "language": detected_lang,
        "duration": round(duration, 2),
        "provider": provider_used,
        "chunks": len(chunks),
    }
