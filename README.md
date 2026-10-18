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
LLM answer (any provider) citing the timestamp.

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

## API (shared by the website and the browser extension)

    uvicorn server:app --port 8000      # docs at http://localhost:8000/docs

| Method | Path | Purpose |
|---|---|---|
| POST | `/index` | `{source, captions?, title?}`, starts indexing in the background, returns `{video_id, status}` |
| GET | `/videos/{id}` | `processing` / `error` with log, or `ready` with chapters (time, title, summary, url) |
| POST | `/videos/{id}/ask` | `{question}` returns answer, timestamp, jump URL and source sections |
| GET | `/videos` | list indexed lectures |

Transcript sources, in order: captions sent by the client (the extension reads them in the
browser, so the server never hits YouTube's IP blocking) -> server-side captions
(youtube-transcript-api, then yt-dlp subtitles) -> audio download + Whisper.
Each video is indexed once and cached, so repeat requests are instant and cost no LLM calls.

## Chrome extension

Adds a panel next to the YouTube player: topic chapters with short summaries (click to jump),
the current chapter highlighted while playing, and Q&A with clickable timestamps.

1. Start the backend: `uvicorn server:app --port 8000`
2. Open `chrome://extensions`, enable **Developer mode**, click **Load unpacked**, pick the `extension/` folder.
3. Open any YouTube lecture and click **Analyze this lecture** in the panel.

The backend URL can be changed from the extension's toolbar popup. Captions are read in the
browser (caption track, then YouTube's transcript panel) and sent to the server; if that fails
the server fetches them itself.

## Run

    streamlit run app.py

or from the command line:

    python cli.py index "https://www.youtube.com/watch?v=..." --model base
    python cli.py ask <video_id> "what is backpropagation?"

Tip: use `tiny`/`base` on CPU for speed; `small`/`medium` for accented speech and technical terms.
