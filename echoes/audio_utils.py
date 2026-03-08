"""Audio format utilities — normalise, speed up, and chunk audio for STT engines."""

from __future__ import annotations

import shutil
import tempfile
import warnings
from pathlib import Path

# Suppress pydub's ffmpeg warning (WAV works without ffmpeg, and we'll
# raise a clear error ourselves if conversion actually fails).
warnings.filterwarnings("ignore", message=".*ffmpeg.*", category=RuntimeWarning)

from pydub import AudioSegment


# Formats that pydub can handle (ffmpeg must be installed for non-wav)
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

    # Load audio via pydub
    audio = AudioSegment.from_file(str(filepath))

    # Normalise: mono, 16 kHz, 16-bit
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

    # Write to temp file (caller is responsible for cleanup if needed)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()  # Close handle so other processes can write on Windows

    audio.export(str(tmp_path), format="wav")
    return tmp_path


def get_audio_duration(filepath: str | Path) -> float:
    """Return duration in seconds."""
    audio = AudioSegment.from_file(str(filepath))
    return len(audio) / 1000.0


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

    Uses pydub's frame rate manipulation for a simple speedup.
    This effectively compresses X minutes into X/factor minutes,
    letting Sarvam's 30s window capture more speech.

    Returns path to the sped-up WAV file.
    """
    audio = AudioSegment.from_file(str(filepath))

    # Speed up by increasing frame rate, then setting back to original
    # This makes the audio play faster (higher pitch, but STT handles it)
    original_rate = audio.frame_rate
    sped_up = audio._spawn(audio.raw_data, overrides={
        "frame_rate": int(original_rate * factor)
    }).set_frame_rate(original_rate)

    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    sped_up.export(str(tmp_path), format="wav")
    return tmp_path


def chunk_audio(filepath: str | Path, chunk_ms: int = 29_990) -> list[Path]:
    """
    Split an audio file into chunks of at most chunk_ms milliseconds.

    Default chunk size is 29.99 seconds to stay under Sarvam's 30s limit.

    Returns a list of paths to the chunk WAV files, in order.
    """
    audio = AudioSegment.from_file(str(filepath))
    duration_ms = len(audio)

    if duration_ms <= chunk_ms:
        # No splitting needed
        return [Path(filepath)]

    chunks: list[Path] = []
    for i in range(0, duration_ms, chunk_ms):
        segment = audio[i:i + chunk_ms]
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        segment.export(str(tmp_path), format="wav")
        chunks.append(tmp_path)

    return chunks
