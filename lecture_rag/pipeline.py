import hashlib
from pathlib import Path

from sentence_transformers import SentenceTransformer

from . import store
from .chunking import topic_chunks
from .utils import fmt_time, timestamp_url, youtube_id

EMBED_MODEL = "all-MiniLM-L6-v2"
_embedder = None


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def resolve_id(source: str) -> str:
    """Stable id: the YouTube id for YouTube links/ids, else a hash of the URL/path."""
    if len(source) == 11 and not Path(source).exists() and "/" not in source:
        return source
    return youtube_id(source) or hashlib.md5(source.encode()).hexdigest()[:11]


def build_index(
    source: str,
    whisper_model: str = "base",
    log=print,
    use_captions: bool = True,
    captions: list[dict] | None = None,
    title: str | None = None,
) -> str:
    """source is a YouTube/NPTEL URL, an 11-char YouTube id, or a local audio/video path.
    YouTube: use captions sent by the client (the extension reads them in the browser),
    else fetch them server-side, else download + Whisper."""
    video_id = resolve_id(source)
    if store.exists(video_id):
        log("Already indexed.")
        return video_id

    segments = None
    is_youtube = not Path(source).exists() and (youtube_id(source) or video_id == source)
    if is_youtube:
        source = f"https://www.youtube.com/watch?v={video_id}"
        from .captions import fetch_captions, merge_lines, video_title

        title = title or video_title(video_id)
        if captions:
            log(f"Using {len(captions)} caption lines sent by the client.")
            segments = merge_lines(captions)
        elif use_captions:
            log("Fetching YouTube captions...")
            segments = fetch_captions(video_id)
            if not segments:
                log("No captions available, falling back to Whisper.")

    if segments is None:
        if Path(source).exists():
            audio, title = Path(source), Path(source).stem
        else:
            from .ingest import download_audio

            log("Downloading audio...")
            audio, title = download_audio(source)
        from .transcribe import transcribe

        log("Transcribing with Whisper (slow on CPU)...")
        segments = transcribe(audio, whisper_model)

    log(f"{len(segments)} segments. Chunking by topic...")
    chunks = topic_chunks(segments, embedder())
    log(f"{len(chunks)} topic chunks. Writing chapter titles and summaries...")
    from .summarize import summarize_chunks

    summarize_chunks(chunks, log=log, embedder=embedder())
    log("Embedding...")
    vectors = embedder().encode([c["text"] for c in chunks], normalize_embeddings=True)
    store.save(video_id, {"title": title, "source": source}, chunks, vectors)
    log("Done.")
    return video_id


def chapters(video_id: str) -> dict:
    meta, chunks, _ = store.load(video_id)
    return {
        "video_id": video_id,
        "title": meta["title"],
        "source": meta["source"],
        "chapters": [
            {
                "time": fmt_time(c["start"]),
                "seconds": int(c["start"]),
                "end_seconds": int(c["end"]),
                "title": c.get("title", ""),
                "summary": c.get("summary", ""),
                "url": timestamp_url(meta["source"], c["start"]),
            }
            for c in chunks
        ],
    }


def retrieve(video_id: str, question: str, k: int = 4) -> tuple[dict, list[dict]]:
    meta, chunks, vectors = store.load(video_id)
    q = embedder().encode([question], normalize_embeddings=True)[0]
    scores = vectors @ q
    top = scores.argsort()[::-1][:k]
    return meta, [{**chunks[i], "score": float(scores[i])} for i in top]


def answer(video_id: str, question: str, k: int = 4) -> dict:
    from .answer import generate

    meta, hits = retrieve(video_id, question, k)
    best = hits[0]
    return {
        "answer": generate(question, hits),
        "timestamp": fmt_time(best["start"]),
        "seconds": int(best["start"]),
        "url": timestamp_url(meta["source"], best["start"]),
        "sources": [
            {
                "time": fmt_time(h["start"]),
                "seconds": int(h["start"]),
                "title": h.get("title", ""),
                "score": round(h["score"], 3),
                "text": h["text"],
            }
            for h in hits
        ],
    }
