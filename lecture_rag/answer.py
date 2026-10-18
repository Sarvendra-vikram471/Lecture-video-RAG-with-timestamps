"""LLM calls behind a swappable provider layer with automatic fallback.

Set LLM_PROVIDERS to a comma-separated priority list, e.g. "groq,ollama,anthropic".
Providers without credentials are skipped; if every provider fails (rate limit, quota,
network) callers get None and use a non-LLM fallback, so the app never breaks.
"""
import os

from .utils import fmt_time

ANSWER_SYSTEM = (
    "You answer questions about a lecture using ONLY the transcript excerpts given. "
    "Each excerpt starts with its timestamp in [mm:ss]. Answer concisely and cite the "
    "timestamp where the topic is explained, e.g. 'explained at 14:32'. If the excerpts "
    "do not contain the answer, say so."
)

# name -> (base_url, api key env var, default model)
OPENAI_COMPATIBLE = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-2.0-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct"),
    "openai": (None, "OPENAI_API_KEY", "gpt-4o-mini"),
    "ollama": ("http://localhost:11434/v1", "OLLAMA_API_KEY", "llama3.2"),  # local, no key
}
DEFAULT_ORDER = "groq,gemini,openrouter,openai,anthropic,ollama"


def _openai_compatible(name: str, system: str, user: str, max_tokens: int) -> str:
    from openai import OpenAI

    base_url, key_env, default_model = OPENAI_COMPATIBLE[name]
    client = OpenAI(base_url=base_url, api_key=os.environ.get(key_env, "ollama"), timeout=60, max_retries=0)
    resp = client.chat.completions.create(
        model=os.environ.get(f"{name.upper()}_MODEL", default_model),
        max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return resp.choices[0].message.content


def _anthropic(system: str, user: str, max_tokens: int) -> str:
    import anthropic

    msg = anthropic.Anthropic(max_retries=0).messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def _available(name: str) -> bool:
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if name == "ollama":
        return bool(os.environ.get("OLLAMA_ENABLED")) or name in os.environ.get("LLM_PROVIDERS", "")
    return name in OPENAI_COMPATIBLE and bool(os.environ.get(OPENAI_COMPATIBLE[name][1]))


def complete(system: str, user: str, max_tokens: int = 600) -> tuple[str | None, list[str]]:
    """Try each configured provider in order. Returns (text or None, list of errors)."""
    order = [p.strip() for p in os.environ.get("LLM_PROVIDERS", DEFAULT_ORDER).split(",") if p.strip()]
    errors = []
    for name in order:
        if not _available(name):
            continue
        try:
            if name == "anthropic":
                return _anthropic(system, user, max_tokens), errors
            return _openai_compatible(name, system, user, max_tokens), errors
        except Exception as e:  # rate limit, quota, network: try the next provider
            errors.append(f"{name}: {type(e).__name__}")
    return None, errors


def generate(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[{fmt_time(h['start'])}] {h['text']}" for h in hits)
    text, errors = complete(ANSWER_SYSTEM, f"Excerpts:\n{context}\n\nQuestion: {question}")
    if text:
        return text

    best = hits[0]
    note = f" ({'; '.join(errors)})" if errors else " (no LLM provider configured)"
    return f"[Showing best matching excerpt{note}]\n\nExplained at {fmt_time(best['start'])}: {best['text']}"
