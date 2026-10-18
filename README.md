---
title: Lecture RAG with Timestamps
emoji: 🎓
colorFrom: blue
colorTo: indigo
sdk: streamlit
sdk_version: 1.40.0
python_version: "3.11"
app_file: app.py
pinned: false
---

# Lecture RAG with timestamp answers

Turns a YouTube/NPTEL lecture (or a local audio/video file) into a searchable index and answers
questions with a jump-to timestamp, e.g. "explained at 14:32".

Flow: yt-dlp audio -> faster-whisper transcript (timed segments) -> topic-based chunking
(new chunk where embedding similarity drops) -> MiniLM embeddings -> cosine retrieval ->
Claude answer citing the timestamp.

## Setup

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    set GROQ_API_KEY=...         (optional; any one provider below is enough)

### LLM providers (all optional, with automatic fallback)

Retrieval and timestamps use local embeddings and need no LLM. Only the answer text does.
Set `LLM_PROVIDERS` to a priority list; providers without a key are skipped, and if all fail the
app still returns the best transcript excerpt + timestamp.

| Provider | Env var | Notes |
|---|---|---|
| groq | `GROQ_API_KEY` | free tier, Llama 3.3 |
| gemini | `GEMINI_API_KEY` | free tier |
| openrouter | `OPENROUTER_API_KEY` | many models |
| openai | `OPENAI_API_KEY` | paid |
| anthropic | `ANTHROPIC_API_KEY` | paid |
| ollama | `OLLAMA_ENABLED=1` | local Llama/Qwen, no key, no limits |

    set LLM_PROVIDERS=groq,ollama,anthropic

## Run

    streamlit run app.py

or from the command line:

    python cli.py index "https://www.youtube.com/watch?v=..." --model base
    python cli.py ask <video_id> "what is backpropagation?"

Tip: use `tiny`/`base` on CPU for speed; `small`/`medium` for accented speech and technical terms.
