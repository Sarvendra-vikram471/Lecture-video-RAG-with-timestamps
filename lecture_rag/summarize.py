"""Short title + summary for each topic chunk (the extension's chapter list)."""
import json
import re

from .answer import complete
from .utils import fmt_time

SYSTEM = (
    "You write chapter markers for a lecture video. For each numbered transcript section, "
    "return a short title (max 6 words) and a one-sentence summary of what is explained. "
    'Respond with ONLY a JSON array: [{"i": 0, "title": "...", "summary": "..."}, ...]'
)
BATCH = 8           # sections per LLM call, keeps requests within free-tier token limits
MAX_CHARS = 1500    # per section sent to the LLM


def _fallback(chunk: dict, embedder=None) -> dict:
    """No LLM: use the sentence closest to the chunk's overall meaning as the summary."""
    sents = [s for s in re.split(r"(?<=[.?!])\s+", chunk["text"].strip()) if len(s.split()) >= 5]
    best = sents[0] if sents else chunk["text"][:200]
    if embedder is not None and len(sents) > 1:
        emb = embedder.encode(sents, normalize_embeddings=True)
        centroid = emb.mean(axis=0)
        best = sents[int((emb @ centroid).argmax())]
    words = best.split()
    return {"title": " ".join(words[:6]) + ("..." if len(words) > 6 else ""), "summary": best[:220]}


def _parse(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else []
    except json.JSONDecodeError:
        return []


def summarize_chunks(chunks: list[dict], log=print, embedder=None) -> list[dict]:
    """Adds 'title' and 'summary' to each chunk. Falls back to the first sentence if no LLM."""
    for b in range(0, len(chunks), BATCH):
        batch = chunks[b:b + BATCH]
        user = "\n\n".join(
            f"Section {i} [{fmt_time(c['start'])}]:\n{c['text'][:MAX_CHARS]}" for i, c in enumerate(batch)
        )
        text, errors = complete(SYSTEM, user, max_tokens=150 * len(batch))
        if errors:
            log(f"LLM fallbacks: {'; '.join(errors)}")
        by_i = {item.get("i"): item for item in _parse(text) if isinstance(item, dict)}
        for i, c in enumerate(batch):
            item = by_i.get(i)
            if item and item.get("title"):
                c["title"], c["summary"] = item["title"], item.get("summary", "")
            else:
                c.update(_fallback(c, embedder))
    return chunks
