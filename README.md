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
    set ANTHROPIC_API_KEY=...    (optional; without it you get the best excerpt + timestamp)

## Run

    streamlit run app.py

or from the command line:

    python cli.py index "https://www.youtube.com/watch?v=..." --model base
    python cli.py ask <video_id> "what is backpropagation?"

Tip: use `tiny`/`base` on CPU for speed; `small`/`medium` for accented speech and technical terms.
