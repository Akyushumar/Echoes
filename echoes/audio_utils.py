"""Audio format utilities — normalise, speed up, and chunk audio for STT engines.
Uses ffmpeg via subprocess to bypass Python's audioop dependencies missing in 3.13+.
"""

from __future__ import annotations

import shutil
import tempfile
import subprocess
from pathlib import Path


# Formats that ffmpeg can handle
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac"}

# ── Audio dir for storing voice notes ──────────────────────────────
AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def ensure_wav(filepath: str | Path) -> Path:
    """
    Convert any supported audio file to 16-bit 16 kHz mono WAV.

    If the file is already a conforming WAV, return it as-is.
    Otherwise write a temp WAV and return the temp path.
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise FileNotFoundError(f"Audio file not found: {filepath}")

    ext = filepath.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported audio format '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    # Normalise: mono, 16 kHz, 16-bit
    cmd = [
        "ffmpeg", "-y", "-i", str(filepath),
        "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
        str(tmp_path)
    ]
    
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return tmp_path


def get_audio_duration(filepath: str | Path) -> float:
    """Return duration in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(filepath)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    return float(result.stdout.strip())


def save_audio_file(filepath: str | Path, entry_id: int) -> str:
    """
    Copy an audio file to data/audio/ with a standardised name.

    Returns the relative path from the project root (e.g. 'data/audio/entry_001.wav').
    """
    filepath = Path(filepath)
    dest_name = f"entry_{entry_id:04d}{filepath.suffix.lower()}"
    dest = AUDIO_DIR / dest_name
    shutil.copy2(str(filepath), str(dest))
    return f"data/audio/{dest_name}"


def speedup_audio(filepath: str | Path, factor: float = 1.25) -> Path:
    """
    Speed up audio by the given factor without changing pitch.

    Uses ffmpeg's atempo filter.
    Returns path to the sped-up WAV file.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = [
        "ffmpeg", "-y", "-i", str(filepath),
        "-filter:a", f"atempo={factor}",
        str(tmp_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return tmp_path


def chunk_audio(filepath: str | Path, chunk_ms: int = 29_990) -> list[Path]:
    """
    Split an audio file into chunks of at most chunk_ms milliseconds.

    Default chunk size is 29.99 seconds to stay under Sarvam's 30s limit.

    Returns a list of paths to the chunk WAV files, in order.
    """
    duration = get_audio_duration(filepath)
    chunk_sec = chunk_ms / 1000.0

    if duration <= chunk_sec:
        # No splitting needed
        return [Path(filepath)]

    # We need a temp directory for the segments
    tmp_dir = Path(tempfile.mkdtemp())
    out_pattern = tmp_dir / "chunk_%03d.wav"

    cmd = [
        "ffmpeg", "-y", "-i", str(filepath),
        "-f", "segment", "-segment_time", str(chunk_sec),
        "-c", "copy",
        str(out_pattern)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Gather generated chunks
    chunks = sorted(list(tmp_dir.glob("chunk_*.wav")))
    return chunks
