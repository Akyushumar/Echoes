"""Echoes — Streamlit Web UI for multilingual voice journaling."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go

from echoes.config import GEMINI_API_KEY, SARVAM_API_KEY, OPENAI_API_KEY, MOOD_TAGS
from echoes.transcribe import transcribe_audio
from echoes.analyse import analyse_emotion
from echoes.models import JournalEntry
from echoes.audio_utils import save_audio_file
from echoes.storage import (
    save_entry, get_entries, get_mood_history,
    get_entry_count, search_entries, get_all_entries, _get_connection,
)

# ── Page Config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Echoes — Voice Journal",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Mood Badge Colours ─────────────────────────────────────────────
MOOD_COLORS = {
    "happy": "#FACC15",
    "excited": "#E879F9",
    "grateful": "#4ADE80",
    "calm": "#22D3EE",
    "reflective": "#60A5FA",
    "hopeful": "#34D399",
    "neutral": "#A3A3A3",
    "anxious": "#FDE047",
    "frustrated": "#F87171",
    "sad": "#93C5FD",
}

MOOD_EMOJI = {
    "happy": "😊", "excited": "🎉", "grateful": "🙏", "calm": "😌",
    "reflective": "🤔", "hopeful": "🌱", "neutral": "😐",
    "anxious": "😰", "frustrated": "😤", "sad": "😢",
}


def mood_badge(mood: str) -> str:
    """Return an HTML mood badge."""
    color = MOOD_COLORS.get(mood, "#A3A3A3")
    emoji = MOOD_EMOJI.get(mood, "")
    return f'<span style="background:{color}20; color:{color}; padding:4px 12px; border-radius:12px; font-weight:600; font-size:0.9em;">{emoji} {mood}</span>'


# ── Custom CSS ─────────────────────────────────────────────────────
st.markdown("""
<style>
    .entry-card {
        background: #1A1A2E;
        border: 1px solid #2A2A3E;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s;
    }
    .entry-card:hover {
        border-color: #7C3AED;
    }
    .entry-date {
        color: #888;
        font-size: 0.85em;
    }
    .entry-transcript {
        color: #E0E0E0;
        margin: 0.5rem 0;
        line-height: 1.6;
    }
    .entry-summary {
        color: #A78BFA;
        font-style: italic;
        border-left: 3px solid #7C3AED;
        padding-left: 0.8rem;
        margin-top: 0.5rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #1A1A2E 0%, #16213E 100%);
        border: 1px solid #2A2A3E;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        color: #7C3AED;
    }
    .stat-label {
        color: #888;
        font-size: 0.85em;
        margin-top: 0.3rem;
    }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F0F1A 0%, #1A1A2E 100%);
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("# 🎙️ Echoes")
    st.caption("Multilingual Voice Journal")
    st.divider()

    page = st.radio(
        "Navigate",
        ["✨ New Entry", "📓 Journal", "📊 Mood Timeline", "🔍 Search"],
        label_visibility="collapsed",
    )

    st.divider()

    # API Status
    st.markdown("##### API Status")
    apis = [
        ("Sarvam AI", bool(SARVAM_API_KEY)),
        ("OpenAI", bool(OPENAI_API_KEY)),
        ("Gemini", bool(GEMINI_API_KEY)),
    ]
    for name, ok in apis:
        icon = "🟢" if ok else "🔴"
        st.markdown(f"{icon} {name}")

    st.divider()
    st.caption(f"Entries: {get_entry_count()}")


# ── Page: New Entry ────────────────────────────────────────────────
if page == "✨ New Entry":
    st.markdown("## ✨ New Journal Entry")
    st.markdown("Upload an audio file or record from your microphone.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📁 Upload Audio")
        uploaded = st.file_uploader(
            "Drop your audio file here",
            type=["wav", "mp3", "m4a", "ogg", "webm", "flac", "aac"],
            label_visibility="collapsed",
        )

    with col2:
        st.markdown("#### 🎤 Record from Mic")
        recorded = st.audio_input("Record a voice note", label_visibility="collapsed")

    # Options
    col_lang, col_tags = st.columns(2)
    with col_lang:
        language = st.selectbox("Language hint (optional)", ["Auto-detect", "en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml"])
        if language == "Auto-detect":
            language = None
    with col_tags:
        tags = st.text_input("Tags (comma-separated)", placeholder="work, reflection, morning")

    # Determine audio source
    audio_source = None
    audio_bytes = None

    if uploaded is not None:
        audio_source = "upload"
        audio_bytes = uploaded.getvalue()
        st.audio(audio_bytes)
    elif recorded is not None:
        audio_source = "mic"
        audio_bytes = recorded.getvalue()
        st.audio(audio_bytes)

    # Process button
    if audio_bytes and st.button("🚀 Process & Save", type="primary", use_container_width=True):
        # Save to temp file
        suffix = ".wav" if audio_source == "mic" else f".{uploaded.name.rsplit('.', 1)[-1]}" if uploaded else ".wav"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(audio_bytes)
        tmp.close()
        tmp_path = Path(tmp.name)

        # Transcribe
        with st.spinner("🎙️ Transcribing audio..."):
            try:
                stt_result = transcribe_audio(tmp_path, language=language)
            except Exception as e:
                st.error(f"Transcription failed: {e}")
                st.stop()

        transcript = stt_result["transcript"]
        if transcript:
            st.markdown("##### Transcript")
            st.info(transcript)
        else:
            st.warning("No speech detected in the audio.")

        # Analyse
        with st.spinner("🧠 Analysing emotion..."):
            try:
                emotion = analyse_emotion(transcript)
            except Exception as e:
                st.error(f"Emotion analysis failed: {e}")
                st.stop()

        # Save entry
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

        # Save audio file
        audio_path = save_audio_file(tmp_path, entry_id)
        conn = _get_connection()
        conn.execute("UPDATE entries SET audio_path = ? WHERE id = ?", (audio_path, entry_id))
        conn.commit()
        conn.close()

        # Success
        st.success(f"Entry #{entry_id} saved!")
        col_m, col_s, col_l = st.columns(3)
        with col_m:
            st.markdown(f"**Mood:** {mood_badge(emotion['mood_tag'])}", unsafe_allow_html=True)
        with col_s:
            st.markdown(f"**Summary:** {emotion['summary']}")
        with col_l:
            chunks = stt_result.get("chunks", 1)
            st.markdown(f"**Provider:** {stt_result['provider']} ({chunks} chunk{'s' if chunks > 1 else ''})")

        st.balloons()


# ── Page: Journal ──────────────────────────────────────────────────
elif page == "📓 Journal":
    st.markdown("## 📓 Journal")

    total = get_entry_count()
    if total == 0:
        st.info("No entries yet. Create one from the **✨ New Entry** page!")
        st.stop()

    count = st.slider("Entries to show", 5, min(total, 50), min(total, 10))
    entries = get_entries(limit=count)

    # Stats row
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""<div class="stat-card">
            <div class="stat-value">{total}</div>
            <div class="stat-label">Total Entries</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        moods = get_mood_history(days=30)
        if moods:
            freq = {}
            for m in moods:
                freq[m["mood_tag"]] = freq.get(m["mood_tag"], 0) + 1
            top_mood = max(freq, key=freq.get)
            emoji = MOOD_EMOJI.get(top_mood, "")
            st.markdown(f"""<div class="stat-card">
                <div class="stat-value">{emoji}</div>
                <div class="stat-label">Top Mood: {top_mood}</div>
            </div>""", unsafe_allow_html=True)
    with col3:
        total_dur = sum(e.audio_duration or 0 for e in entries)
        st.markdown(f"""<div class="stat-card">
            <div class="stat-value">{total_dur:.0f}s</div>
            <div class="stat-label">Audio Recorded</div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    # Entry cards
    for e in entries:
        try:
            dt = datetime.fromisoformat(e.timestamp)
            date_str = dt.strftime("%B %d, %Y at %H:%M")
        except ValueError:
            date_str = e.timestamp[:16]

        with st.container():
            st.markdown(f"""<div class="entry-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span class="entry-date">📅 {date_str}</span>
                    {mood_badge(e.mood_tag)}
                </div>
                <div class="entry-transcript">{e.transcript if e.transcript else '<em>No transcript</em>'}</div>
                <div class="entry-summary">💭 {e.summary}</div>
            </div>""", unsafe_allow_html=True)

            # Audio playback
            if e.audio_path:
                audio_file = Path(__file__).parent / e.audio_path
                if audio_file.exists():
                    st.audio(str(audio_file))


# ── Page: Mood Timeline ───────────────────────────────────────────
elif page == "📊 Mood Timeline":
    st.markdown("## 📊 Mood Timeline")

    days = st.slider("Look back (days)", 7, 90, 30)
    history = get_mood_history(days=days)

    if not history:
        st.info("No mood data yet. Add some entries first!")
        st.stop()

    # Mood distribution bar chart
    freq = {}
    for record in history:
        tag = record["mood_tag"]
        freq[tag] = freq.get(tag, 0) + 1

    sorted_moods = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    labels = [f"{MOOD_EMOJI.get(m, '')} {m}" for m, _ in sorted_moods]
    values = [c for _, c in sorted_moods]
    colors = [MOOD_COLORS.get(m, "#A3A3A3") for m, _ in sorted_moods]

    fig_bar = go.Figure(go.Bar(
        x=values,
        y=labels,
        orientation="h",
        marker=dict(color=colors, line=dict(width=0)),
        text=values,
        textposition="auto",
    ))
    fig_bar.update_layout(
        title="Mood Distribution",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(300, len(sorted_moods) * 50),
        yaxis=dict(autorange="reversed"),
        xaxis_title="Count",
        margin=dict(l=120),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # Timeline scatter
    dates = []
    mood_values = []
    mood_labels = []
    mood_colors_list = []

    mood_y_map = {m: i for i, m in enumerate(MOOD_TAGS)}

    for record in history:
        try:
            dt = datetime.fromisoformat(record["timestamp"])
        except ValueError:
            continue
        dates.append(dt)
        tag = record["mood_tag"]
        mood_values.append(mood_y_map.get(tag, 5))
        mood_labels.append(f"{MOOD_EMOJI.get(tag, '')} {tag}")
        mood_colors_list.append(MOOD_COLORS.get(tag, "#A3A3A3"))

    if dates:
        fig_timeline = go.Figure(go.Scatter(
            x=dates,
            y=mood_labels,
            mode="markers+lines",
            marker=dict(size=12, color=mood_colors_list, line=dict(width=1, color="#333")),
            line=dict(color="rgba(124, 58, 237, 0.25)", width=1),
            hovertemplate="%{y}<br>%{x|%b %d, %H:%M}<extra></extra>",
        ))
        fig_timeline.update_layout(
            title="Mood Over Time",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            xaxis_title="Date",
            yaxis_title="",
            margin=dict(l=120),
        )
        st.plotly_chart(fig_timeline, use_container_width=True)


# ── Page: Search ───────────────────────────────────────────────────
elif page == "🔍 Search":
    st.markdown("## 🔍 Search Entries")

    col1, col2 = st.columns(2)
    with col1:
        keyword = st.text_input("Keyword", placeholder="Search transcripts & summaries...")
        mood_filter = st.selectbox("Mood", ["All"] + MOOD_TAGS)
    with col2:
        date_from = st.date_input("From", value=datetime.now().date() - timedelta(days=30))
        date_to = st.date_input("To", value=datetime.now().date())

    if st.button("🔍 Search", type="primary", use_container_width=True):
        results = search_entries(
            keyword=keyword if keyword else None,
            mood_tag=mood_filter if mood_filter != "All" else None,
            date_from=str(date_from) if date_from else None,
            date_to=str(date_to) + "T23:59:59" if date_to else None,
        )

        if not results:
            st.info("No matching entries found.")
        else:
            st.markdown(f"**{len(results)} results found**")
            for e in results:
                try:
                    dt = datetime.fromisoformat(e.timestamp)
                    date_str = dt.strftime("%B %d, %Y at %H:%M")
                except ValueError:
                    date_str = e.timestamp[:16]

                with st.container():
                    st.markdown(f"""<div class="entry-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="entry-date">📅 {date_str}</span>
                            {mood_badge(e.mood_tag)}
                        </div>
                        <div class="entry-transcript">{e.transcript if e.transcript else '<em>No transcript</em>'}</div>
                        <div class="entry-summary">💭 {e.summary}</div>
                    </div>""", unsafe_allow_html=True)

                    if e.audio_path:
                        audio_file = Path(__file__).parent / e.audio_path
                        if audio_file.exists():
                            st.audio(str(audio_file))
