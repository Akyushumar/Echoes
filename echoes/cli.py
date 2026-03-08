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
from echoes.storage import save_entry, get_entries, get_mood_history, get_entry_count, search_entries, get_all_entries

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


def _print_entries_table(entries: list, title: str) -> None:
    """Shared helper to display entries in a Rich table."""
    table = Table(title=title, show_lines=True)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Date", width=18)
    table.add_column("Mood", width=12)
    table.add_column("Transcript", max_width=50)
    table.add_column("Summary", max_width=40)

    for e in entries:
        try:
            dt = datetime.fromisoformat(e.timestamp)
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            date_str = e.timestamp[:16]

        preview = e.transcript[:80] + ("..." if len(e.transcript) > 80 else "")
        table.add_row(
            str(e.id),
            date_str,
            _mood_styled(e.mood_tag),
            preview,
            e.summary[:60] + ("..." if len(e.summary) > 60 else ""),
        )

    console.print(table)


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
    console.print(f"   Language: {stt_result['language']} ({stt_result['provider']})")


@app.command()
def record(
    language: Optional[str] = typer.Option(
        None, "--lang", "-l", help="ISO-639-1 language hint."
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Comma-separated tags."
    ),
    duration: int = typer.Option(
        300, "--duration", "-d", help="Max recording duration in seconds."
    ),
):
    """Record from microphone, transcribe, analyse, and save."""
    from echoes.recorder import record_audio

    wav_path = record_audio(max_duration=duration)
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        console.print("[red]Recording cancelled or empty.[/red]")
        raise typer.Exit(1)

    # Feed into the same pipeline as 'add'
    with console.status("[bold cyan]Transcribing...[/bold cyan]"):
        try:
            stt_result = transcribe_audio(wav_path, language=language)
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


@app.command()
def transcribe(
    file: Path = typer.Argument(..., help="Path to an audio file to transcribe."),
    language: Optional[str] = typer.Option(
        None, "--lang", "-l", help="ISO-639-1 language hint (e.g. 'en', 'hi')."
    ),
    model: str = typer.Option(
        "base", "--model", "-m", help="Whisper model size for local fallback (tiny, base, etc.)."
    ),
):
    """Only transcribe an audio file (no analysis or saving)."""
    if not file.exists():
        console.print(f"[red][X] File not found: {file}[/red]")
        raise typer.Exit(1)

    with console.status(f"[bold cyan]Transcribing {file.name}...[/bold cyan]"):
        try:
            stt_result = transcribe_audio(file, language=language, model_name=model)
        except Exception as e:
            console.print(f"[red][X] Transcription failed: {e}[/red]")
            raise typer.Exit(1)

    console.print()
    console.print(Panel(
        stt_result["transcript"],
        title=f"Transcript ({stt_result['language']} | {stt_result['provider']})",
        border_style="cyan"
    ))
    console.print(f"Duration: {stt_result['duration']}s")


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
    _print_entries_table(entries, f"Journal Entries (showing {len(entries)} of {total})")


@app.command()
def search(
    keyword: Optional[str] = typer.Option(None, "--keyword", "-k", help="Search in transcript/summary/tags."),
    mood: Optional[str] = typer.Option(None, "--mood", "-m", help="Filter by mood tag."),
    date_from: Optional[str] = typer.Option(None, "--from", help="Start date (YYYY-MM-DD)."),
    date_to: Optional[str] = typer.Option(None, "--to", help="End date (YYYY-MM-DD)."),
):
    """Search journal entries by keyword, mood, or date range."""
    if not any([keyword, mood, date_from, date_to]):
        console.print("[dim]Provide at least one filter: --keyword, --mood, --from, --to[/dim]")
        raise typer.Exit(1)

    results = search_entries(keyword=keyword, mood_tag=mood, date_from=date_from, date_to=date_to)
    if not results:
        console.print("[dim]No matching entries found.[/dim]")
        raise typer.Exit()

    _print_entries_table(results, f"Search Results ({len(results)} matches)")


@app.command()
def export(
    output: Path = typer.Option("journal_export.md", "--output", "-o", help="Output Markdown file path."),
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Only export last N days."),
):
    """Export journal entries to a Markdown file."""
    if days:
        from echoes.storage import search_entries as _search
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        entries = _search(date_from=cutoff)
    else:
        entries = get_all_entries()

    if not entries:
        console.print("[dim]No entries to export.[/dim]")
        raise typer.Exit()

    lines = [f"# Echoes Journal Export\n", f"*{len(entries)} entries*\n\n---\n"]

    for e in entries:
        try:
            dt = datetime.fromisoformat(e.timestamp)
            date_str = dt.strftime("%B %d, %Y at %H:%M")
        except ValueError:
            date_str = e.timestamp

        lines.append(f"\n## {date_str}\n")
        lines.append(f"**Mood:** {e.mood_tag} ({e.confidence:.0%} confidence)\n")
        if e.tags:
            lines.append(f"**Tags:** {e.tags}\n")
        lines.append(f"\n{e.transcript}\n")
        if e.summary:
            lines.append(f"\n> {e.summary}\n")
        lines.append("\n---\n")

    output.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[bold green][OK] Exported {len(entries)} entries to {output}[/bold green]")


@app.command()
def mood(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to look back."),
):
    """Show mood history over time."""
    history = get_mood_history(days=days)
    if not history:
        console.print("[dim]No mood data yet.[/dim]")
        raise typer.Exit()

    freq: dict[str, int] = {}
    for record in history:
        tag = record["mood_tag"]
        freq[tag] = freq.get(tag, 0) + 1

    console.print(Panel(
        f"Mood distribution over the last {days} days ({len(history)} entries)",
        title="Mood History",
        border_style="magenta",
    ))

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
