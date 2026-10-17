"""Topic-based chunking: start a new chunk where adjacent segments stop being similar."""
import numpy as np


def topic_chunks(
    segments: list[dict],
    embedder,
    window: int = 3,
    min_sec: float = 30,
    max_sec: float = 240,
    sensitivity: float = 1.0,
) -> list[dict]:
    """Boundaries are gaps where the similarity between the `window` segments before and
    after drops below (mean - sensitivity * std) for the lecture. min/max duration keep
    chunks usable as timestamp citations."""
    n = len(segments)
    if n == 0:
        return []
    emb = embedder.encode([s["text"] for s in segments], normalize_embeddings=True)

    sims = []
    for i in range(1, n):
        a = emb[max(0, i - window):i].mean(axis=0)
        b = emb[i:i + window].mean(axis=0)
        sims.append(float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9)))
    sims = np.array(sims) if sims else np.array([1.0])
    threshold = sims.mean() - sensitivity * sims.std()

    groups, cur = [], [segments[0]]
    for i in range(1, n):
        dur = cur[-1]["end"] - cur[0]["start"]
        lo, hi = max(0, i - 1 - window), i + window
        is_dip = sims[i - 1] < threshold and sims[i - 1] <= sims[lo:hi].min()
        boundary = is_dip and dur >= min_sec
        if boundary or dur >= max_sec:
            groups.append(cur)
            cur = []
        cur.append(segments[i])
    if groups and cur[-1]["end"] - cur[0]["start"] < min_sec:
        groups[-1].extend(cur)
    else:
        groups.append(cur)

    return [
        {
            "start": g[0]["start"],
            "end": g[-1]["end"],
            "text": " ".join(s["text"] for s in g),
        }
        for g in groups
    ]
