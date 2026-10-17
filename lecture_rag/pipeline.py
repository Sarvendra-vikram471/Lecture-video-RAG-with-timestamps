import hashlib
from pathlib import Path

from sentence_transformers import SentenceTransformer

from . import store
from .chunking import topic_chunks
from .ingest import download_audio
from .transcribe import transcribe
from .utils import fmt_time, timestamp_url, youtube_id

EMBED_MODEL = "all-MiniLM-L6-v2"
_embedder = None


def embedder():
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def build_index(source: str, whisper_model: str = "small", log=print) -> str:
    """source is a YouTube/NPTEL URL or a local audio/video file path. Returns the video id."""
    if Path(source).exists():
        audio, title = Path(source), Path(source).stem
        video_id = hashlib.md5(source.encode()).hexdigest()[:11]
    else:
        video_id = youtube_id(source) or hashlib.md5(source.encode()).hexdigest()[:11]
        if store.exists(video_id):
            log("Already indexed.")
            return video_id
        log("Downloading audio...")
        audio, title = download_audio(source)

    log("Transcribing with Whisper (slow on CPU)...")
    segments = transcribe(audio, whisper_model)
    log(f"{len(segments)} segments. Chunking by topic...")
    chunks = topic_chunks(segments, embedder())
    log(f"{len(chunks)} topic chunks. Embedding...")
    vectors = embedder().encode([c["text"] for c in chunks], normalize_embeddings=True)
    store.save(video_id, {"title": title, "source": source}, chunks, vectors)
    return video_id


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
                "score": round(h["score"], 3),
                "text": h["text"],
            }
            for h in hits
        ],
    }
