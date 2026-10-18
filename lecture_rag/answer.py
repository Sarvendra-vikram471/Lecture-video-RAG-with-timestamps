"""Answer generation behind a swappable provider layer with automatic fallback.

Set LLM_PROVIDERS to a comma-separated priority list, e.g. "groq,ollama,anthropic".
Providers without credentials are skipped; if every provider fails (rate limit, quota,
network) the answer falls back to the best transcript excerpt, so the app never breaks.
"""
import os

from .utils import fmt_time

SYSTEM = (
    "You answer questions about a lecture using ONLY the transcript excerpts given. "
    "Each excerpt starts with its timestamp in [mm:ss]. Answer concisely and cite the "
    "timestamp where the topic is explained, e.g. 'explained at 14:32'. If the excerpts "
    "do not contain the answer, say so."
)

# name -> (base_url, api key env var, default model, key required)
OPENAI_COMPATIBLE = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.3-70b-versatile", True),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-2.0-flash", True),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct", True),
    "openai": (None, "OPENAI_API_KEY", "gpt-4o-mini", True),
    "ollama": ("http://localhost:11434/v1", "OLLAMA_API_KEY", "llama3.2", False),  # local, no key
}
DEFAULT_ORDER = "groq,gemini,openrouter,openai,anthropic,ollama"


def _openai_compatible(name: str, user_msg: str) -> str:
    from openai import OpenAI

    base_url, key_env, default_model, _ = OPENAI_COMPATIBLE[name]
    client = OpenAI(base_url=base_url, api_key=os.environ.get(key_env, "ollama"), timeout=60)
    model = os.environ.get(f"{name.upper()}_MODEL", default_model)
    resp = client.chat.completions.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_msg}],
    )
    return resp.choices[0].message.content


def _anthropic(user_msg: str) -> str:
    import anthropic

    msg = anthropic.Anthropic().messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return msg.content[0].text


def _available(name: str) -> bool:
    if name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    if name == "ollama":
        return bool(os.environ.get("OLLAMA_ENABLED")) or name in os.environ.get("LLM_PROVIDERS", "")
    return name in OPENAI_COMPATIBLE and bool(os.environ.get(OPENAI_COMPATIBLE[name][1]))


def generate(question: str, hits: list[dict]) -> str:
    context = "\n\n".join(f"[{fmt_time(h['start'])}] {h['text']}" for h in hits)
    user_msg = f"Excerpts:\n{context}\n\nQuestion: {question}"

    order = [p.strip() for p in os.environ.get("LLM_PROVIDERS", DEFAULT_ORDER).split(",") if p.strip()]
    errors = []
    for name in order:
        if not _available(name):
            continue
        try:
            return _anthropic(user_msg) if name == "anthropic" else _openai_compatible(name, user_msg)
        except Exception as e:  # rate limit, quota, network: try the next provider
            errors.append(f"{name}: {type(e).__name__}")

    best = hits[0]
    note = f" ({'; '.join(errors)})" if errors else " (no LLM provider configured)"
    return f"[Showing best matching excerpt{note}]\n\nExplained at {fmt_time(best['start'])}: {best['text']}"
