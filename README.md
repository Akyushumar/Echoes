# Echoes 🎙️

**A multilingual voice journaling assistant** that converts spoken thoughts into structured, emotionally-tagged journal entries. Built for anyone who thinks and feels in more than one language.

Speak freely — in any language — and get back a clean transcript, an emotional summary, and a mood tag. All entries are saved locally and trackable over time.

---

## Features

| Feature | Description |
|---|---|
| **Triple STT Pipeline** | Sarvam AI (Indic) → OpenAI Whisper API → Local Whisper — automatic fallback |
| **Audio Preprocessing** | 1.25x speedup + 29.99s chunking to maximise transcription quality |
| **Emotion Analysis** | Gemini 2.0 Flash tags mood from a fixed 10-mood taxonomy |
| **Audio Storage** | Voice notes saved to `data/audio/` with DB references |
| **SQLite Journal** | All entries stored locally with full CRUD + search |
| **Markdown Export** | Export your journal to `.md` for sharing or backup |
| **Live Mic Recording** | Record directly from your microphone |
| **Rich CLI** | Beautiful terminal output with colours and tables |

---

## Quick Start

### Prerequisites

- **Python 3.10+**
- **ffmpeg** — Install via `winget install Gyan.FFmpeg` (Windows) or `brew install ffmpeg` (Mac)

### Setup

```bash
# Clone the repo
git clone https://github.com/Akyushumar/Echoes.git
cd Echoes

# Create virtual environment
python -m venv myenv
myenv\Scripts\activate    # Windows
# source myenv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SARVAM_API_KEY=your_sarvam_api_key_here
OPENAI_API_KEY=your_openai_api_key_here    # optional
```

- **GEMINI_API_KEY** (required) — Get from [Google AI Studio](https://aistudio.google.com/apikey)
- **SARVAM_API_KEY** (recommended) — Get from [Sarvam AI](https://www.sarvam.ai/) — best for Hindi, Tamil, Bengali, etc.
- **OPENAI_API_KEY** (optional) — Falls back to local Whisper if not set

---

## Usage

### Add a journal entry from an audio file

```bash
python -m echoes add path/to/audio.mp3
python -m echoes add recording.wav --lang hi --tags "work,reflection"
```

### Record from your microphone

```bash
python -m echoes record
python -m echoes record --lang en --tags "morning"
```

### Transcribe only (no saving)

```bash
python -m echoes transcribe audio.wav
```

### View your journal

```bash
python -m echoes list              # Recent entries
python -m echoes list --count 20   # Last 20 entries
```

### Search entries

```bash
python -m echoes search --keyword "happy"
python -m echoes search --mood sad
python -m echoes search --from 2026-03-01 --to 2026-03-08
```

### Mood history

```bash
python -m echoes mood              # Last 30 days
python -m echoes mood --days 7     # Last week
```

### Export to Markdown

```bash
python -m echoes export
python -m echoes export --output my_journal.md --days 30
```

---

## Architecture

```
echoes/
├── __init__.py        # Package version
├── __main__.py        # python -m echoes entry point
├── config.py          # API keys, mood taxonomy, paths
├── models.py          # MoodTag enum + JournalEntry dataclass
├── storage.py         # SQLite CRUD + search + export
├── audio_utils.py     # WAV conversion, 1.25x speedup, 29.99s chunking
├── transcribe.py      # Triple STT: Sarvam → OpenAI → Local Whisper
├── analyse.py         # Gemini 2.0 Flash emotion analysis
├── recorder.py        # Live mic recording (sounddevice)
└── cli.py             # Typer CLI with Rich output
```

### How It Works

```
Audio File ──→ Normalise to WAV
                    │
                    ▼
            Speed up 1.25x
                    │
                    ▼
          Chunk into ≤29.99s
                    │
           ┌────────┼────────┐
           ▼        ▼        ▼
        Chunk 1  Chunk 2  Chunk N
           │        │        │
           ▼        ▼        ▼
     ┌─ Sarvam AI (primary) ─────┐
     │  └─ OpenAI API (fallback) │
     │     └─ Local Whisper ─────│
     └───────────────────────────┘
                    │
                    ▼
          Stitch Transcripts
                    │
                    ▼
        Gemini Emotion Analysis
                    │
                    ▼
          Save to SQLite + Audio
```

### Mood Taxonomy

Echoes uses a fixed 10-mood taxonomy for consistent emotion tracking:

`happy` · `excited` · `grateful` · `calm` · `reflective` · `hopeful` · `neutral` · `anxious` · `frustrated` · `sad`

---

## Development Phases

### Phase 1 — Core Pipeline ✅
- Modular package structure (`echoes/`)
- Whisper STT (local, no API key needed)
- Gemini 2.0 Flash emotion analysis
- SQLite storage with CRUD operations
- Typer CLI with Rich terminal output
- Windows Unicode encoding fix

### Phase 2 — Polish & Features ✅
- **Sarvam AI** as primary STT for Indic languages
- Triple STT pipeline with automatic fallback
- Audio preprocessing: 1.25x speedup + 29.99s chunking
- Audio file storage in `data/audio/`
- `echoes record` — live mic recording
- `echoes transcribe` — standalone transcription
- `echoes search` — keyword, mood, and date filtering
- `echoes export` — journal to Markdown

### Phase 3 — Streamlit UI (Planned)
- Web interface wrapping the CLI library
- Audio upload + browser mic recording
- Interactive mood timeline with Plotly
- Deploy to Streamlit Cloud

---

## Tech Stack

| Component | Technology |
|---|---|
| STT (Primary) | Sarvam AI (`saaras:v3`) |
| STT (Fallback 1) | OpenAI Whisper API |
| STT (Fallback 2) | Local Whisper (`openai-whisper`) |
| Emotion Analysis | Google Gemini 2.0 Flash |
| Database | SQLite3 |
| CLI | Typer + Rich |
| Audio Processing | pydub + ffmpeg |
| Mic Recording | sounddevice + scipy |

---

## License

MIT

---

*Built with ❤️ for multilingual journaling.*