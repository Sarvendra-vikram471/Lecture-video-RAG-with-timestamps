"""Answer generation. Uses Claude if ANTHROPIC_API_KEY is set, else returns the best excerpt."""
import os

from .utils import fmt_time

MODEL = os.environ.get("LECTURE_RAG_MODEL", "claude-sonnet-5-5")


def generate(question: str, hits: list[dict]) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        h = hits[0]
        return (
            "(No ANTHROPIC_API_KEY set, showing the best matching excerpt.)\n\n"
            f"Explained at {fmt_time(h['start'])}: {h['text']}"
        )

    import anthropic

    context = "\n\n".join(f"[{fmt_time(h['start'])}] {h['text']}" for h in hits)
    msg = anthropic.Anthropic().messages.create(
        model=MODEL,
        max_tokens=600,
        system=(
            "You answer questions about a lecture using ONLY the transcript excerpts given. "
            "Each excerpt starts with its timestamp in [mm:ss]. Answer concisely and cite the "
            "timestamp where the topic is explained, e.g. 'explained at 14:32'. If the excerpts "
            "do not contain the answer, say so."
        ),
        messages=[{"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {question}"}],
    )
    return msg.content[0].text
