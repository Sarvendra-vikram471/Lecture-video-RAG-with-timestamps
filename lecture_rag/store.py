"""Tiny vector store: numpy matrix + JSON metadata, one folder per video."""
import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


def _dir(video_id: str) -> Path:
    d = DATA / "index" / video_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(video_id: str, meta: dict, chunks: list[dict], vectors: np.ndarray):
    d = _dir(video_id)
    np.save(d / "vectors.npy", vectors)
    (d / "chunks.json").write_text(json.dumps({"meta": meta, "chunks": chunks}), encoding="utf-8")


def exists(video_id: str) -> bool:
    return (DATA / "index" / video_id / "chunks.json").exists()


def load(video_id: str):
    d = DATA / "index" / video_id
    blob = json.loads((d / "chunks.json").read_text(encoding="utf-8"))
    return blob["meta"], blob["chunks"], np.load(d / "vectors.npy")


def list_videos() -> dict[str, str]:
    out = {}
    for f in (DATA / "index").glob("*/chunks.json"):
        out[f.parent.name] = json.loads(f.read_text(encoding="utf-8"))["meta"]["title"]
    return out
