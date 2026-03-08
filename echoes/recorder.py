"""Live microphone recording for Echoes."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from rich.console import Console
from rich.live import Live
from rich.text import Text

console = Console(force_terminal=True)

SAMPLE_RATE = 16000  # 16 kHz mono, matching Whisper expectations


def record_audio(max_duration: int = 300) -> Path:
    """
    Record audio from the default microphone until the user presses Enter.

    Args:
        max_duration: Maximum recording duration in seconds (safety limit).

    Returns:
        Path to the recorded WAV file.
    """
    frames: list[np.ndarray] = []
    stop_event = threading.Event()

    def _callback(indata, frame_count, time_info, status):
        if status:
            pass  # Ignore minor status warnings
        frames.append(indata.copy())

    # Start recording in a background stream
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        callback=_callback,
    )

    console.print("[bold cyan]Recording... Press Enter to stop.[/bold cyan]")
    stream.start()

    # Show a live timer
    try:
        with Live(Text("  0s recorded", style="dim"), console=console, refresh_per_second=2) as live:
            elapsed = 0
            while elapsed < max_duration:
                if stop_event.is_set():
                    break
                # Check for Enter key (non-blocking via short timeout)
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key in (b'\r', b'\n'):
                        break
                import time
                time.sleep(0.5)
                elapsed += 0.5
                live.update(Text(f"  {int(elapsed)}s recorded", style="dim"))
    finally:
        stream.stop()
        stream.close()

    if not frames:
        console.print("[red]No audio captured.[/red]")
        return Path("")

    # Concatenate all frames and save to temp WAV
    audio_data = np.concatenate(frames, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir=str(Path(tempfile.gettempdir())))
    wavfile.write(tmp.name, SAMPLE_RATE, audio_data)

    console.print(f"[green]Captured {int(len(audio_data) / SAMPLE_RATE)}s of audio.[/green]")
    return Path(tmp.name)
