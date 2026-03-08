"""Echoes CLI — Voice journaling from the terminal."""

from __future__ import annotations

import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Fix Windows console encoding for Unicode/emoji output
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from echoes import __version__
from echoes.transcribe import transcribe_audio
from echoes.analyse import analyse_emotion
from echoes.models import JournalEntry
from echoes.storage import save_entry, get_entries, get_mood_history, get_entry_count

app = typer.Typer(
    name="echoes",
    help="Echoes -- Multilingual Voice Journaling Assistant",
    add_completion=False,
)
console = Console(force_terminal=True)


# ── Mood tag colours ────────────────────────────────────────────────
_MOOD_COLORS = {
    "happy": "bright_yellow",
    "excited": "bright_magenta",
    "grateful": "bright_green",
    "calm": "bright_cyan",
    "reflective": "blue",
    "hopeful": "green",
    "neutral": "white",
    "anxious": "yellow",
    "frustrated": "red",
    "sad": "bright_blue",
}


def _mood_styled(mood: str) -> Text:
    color = _MOOD_COLORS.get(mood, "white")
    return Text(mood, style=f"bold {color}")


# ── Commands ────────────────────────────────────────────────────────
@app.command()
def add(
    file: Path = typer.Argument(..., help="Path to an audio file to journal."),
    language: Optional[str] = typer.Option(
        None, "--lang", "-l", help="ISO-639-1 language hint (e.g. 'en', 'hi')."
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Comma-separated tags (e.g. 'work,health')."
    ),
):
    """Transcribe an audio file, analyse emotion, and save as a journal entry."""
    if not file.exists():
        console.print(f"[red][X] File not found: {file}[/red]")
        raise typer.Exit(1)

    with console.status("[bold cyan]Transcribing audio...[/bold cyan]"):
        try:
            stt_result = transcribe_audio(file, language=language)
        except Exception as e:
            console.print(f"[red][X] Transcription failed: {e}[/red]")
            raise typer.Exit(1)

    transcript = stt_result["transcript"]
    console.print(Panel(transcript, title="Transcript", border_style="cyan"))

    with console.status("[bold magenta]Analysing emotion...[/bold magenta]"):
        try:
            emotion = analyse_emotion(transcript)
        except Exception as e:
            console.print(f"[red][X] Emotion analysis failed: {e}[/red]")
            raise typer.Exit(1)

    # Build and save entry
    entry = JournalEntry(
        transcript=transcript,
        language=stt_result["language"],
        mood_tag=emotion["mood_tag"],
        confidence=emotion["confidence"],
        summary=emotion["summary"],
        tags=tags or "",
        audio_duration=stt_result["duration"],
    )

    entry_id = save_entry(entry)
    console.print()
    console.print(f"[bold green][OK] Entry #{entry_id} saved![/bold green]")
    console.print(f"   Mood: ", end="")
    console.print(_mood_styled(emotion["mood_tag"]), end="")
    console.print(f" (confidence: {emotion['confidence']:.0%})")
    console.print(f"   Summary: {emotion['summary']}")
    console.print(f"   Language: {stt_result['language']}")


@app.command(name="list")
def list_entries(
    count: int = typer.Option(10, "--count", "-n", help="Number of entries to show."),
):
    """Show recent journal entries."""
    entries = get_entries(limit=count)
    if not entries:
        console.print("[dim]No entries yet. Use [bold]echoes add <file>[/bold] to create one.[/dim]")
        raise typer.Exit()

    total = get_entry_count()
    table = Table(
        title=f"Journal Entries (showing {len(entries)} of {total})",
        show_lines=True,
    )
    table.add_column("ID", style="dim", width=4)
    table.add_column("Date", width=18)
    table.add_column("Mood", width=12)
    table.add_column("Transcript", max_width=50)
    table.add_column("Summary", max_width=40)

    for e in entries:
        # Format timestamp
        try:
            dt = datetime.fromisoformat(e.timestamp)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            date_str = e.timestamp[:16]

        # Truncate transcript
        preview = e.transcript[:80] + ("..." if len(e.transcript) > 80 else "")

        table.add_row(
            str(e.id),
            date_str,
            _mood_styled(e.mood_tag),
            preview,
            e.summary[:60] + ("..." if len(e.summary) > 60 else ""),
        )

    console.print(table)


@app.command()
def mood(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to look back."),
):
    """Show mood history over time."""
    history = get_mood_history(days=days)
    if not history:
        console.print("[dim]No mood data yet.[/dim]")
        raise typer.Exit()

    # Frequency count
    freq: dict[str, int] = {}
    for record in history:
        tag = record["mood_tag"]
        freq[tag] = freq.get(tag, 0) + 1

    console.print(Panel(
        f"Mood distribution over the last {days} days ({len(history)} entries)",
        title="Mood History",
        border_style="magenta",
    ))

    # Sort by frequency
    for tag, count in sorted(freq.items(), key=lambda x: x[1], reverse=True):
        bar = "#" * count
        pct = count / len(history) * 100
        label = tag.rjust(12)
        console.print(f"  {label}  {bar}  {count} ({pct:.0f}%)")

    console.print()


@app.command()
def version():
    """Show Echoes version."""
    console.print(f"[bold cyan]Echoes[/bold cyan] v{__version__}")


# ── Entry point ─────────────────────────────────────────────────────
def main():
    app()


if __name__ == "__main__":
    main()
