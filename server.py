"""REST API shared by the website and the browser extension.

Run:  uvicorn server:app --port 8000
Docs: http://localhost:8000/docs
"""
import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from lecture_rag import store
from lecture_rag.pipeline import answer, build_index, chapters, resolve_id

app = FastAPI(title="Lecture RAG API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.youtube.com", "http://localhost:8501"],
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Indexing can take minutes (Whisper), so it runs in the background and clients poll.
_pool = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, dict] = {}  # video_id -> {"status": "processing"|"error", "log": [...], "error": str}
_lock = threading.Lock()


class IndexRequest(BaseModel):
    source: str              # YouTube URL/id, NPTEL URL, or server-side file path
    whisper_model: str = "base"
    title: str | None = None
    # Caption lines read in the browser by the extension: [{start, duration, text}].
    # Lets the server skip YouTube entirely (YouTube often blocks server IPs).
    captions: list[dict] | None = None


class AskRequest(BaseModel):
    question: str
    k: int = 4


def _run(video_id: str, req: IndexRequest):
    job = _jobs[video_id]
    try:
        build_index(
            req.source, req.whisper_model, log=job["log"].append, captions=req.captions, title=req.title
        )
        with _lock:
            _jobs.pop(video_id, None)
    except Exception as e:
        job.update(status="error", error=f"{type(e).__name__}: {e}")


@app.post("/index")
def index(req: IndexRequest):
    video_id = resolve_id(req.source)
    if store.exists(video_id):
        return {"video_id": video_id, "status": "ready"}
    with _lock:
        job = _jobs.get(video_id)
        if job and job["status"] == "processing":
            return {"video_id": video_id, "status": "processing"}
        _jobs[video_id] = {"status": "processing", "log": [], "error": None}
    _pool.submit(_run, video_id, req)
    return {"video_id": video_id, "status": "processing"}


@app.get("/videos/{video_id}")
def status(video_id: str):
    if store.exists(video_id):
        return {"video_id": video_id, "status": "ready", **chapters(video_id)}
    job = _jobs.get(video_id)
    if not job:
        raise HTTPException(404, "Not indexed. POST /index first.")
    return {"video_id": video_id, **job}


@app.post("/videos/{video_id}/ask")
def ask(video_id: str, req: AskRequest):
    if not store.exists(video_id):
        raise HTTPException(404, "Not indexed yet.")
    if not req.question.strip():
        raise HTTPException(400, "Empty question.")
    return answer(video_id, req.question, req.k)


@app.get("/videos")
def videos():
    return [{"video_id": v, "title": t} for v, t in store.list_videos().items()]


@app.get("/health")
def health():
    return {"ok": True}
