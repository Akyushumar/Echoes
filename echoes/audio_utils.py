"""Audio format utilities — normalise any audio to WAV for STT engines."""

from __future__ import annotations

import tempfile
import warnings
from pathlib import Path

# Suppress pydub's ffmpeg warning (WAV works without ffmpeg, and we'll
# raise a clear error ourselves if conversion actually fails).
warnings.filterwarnings("ignore", message=".*ffmpeg.*", category=RuntimeWarning)

from pydub import AudioSegment


# Formats that pydub can handle (ffmpeg must be installed for non-wav)
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac", ".aac"}


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
