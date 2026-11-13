"""LLM connection for FRESH-RAG with a swappable provider.

.env settings:
    LLM_PROVIDER=groq          # groq | gemini | openrouter | bedrock
    GROQ_API_KEY=...           # or GEMINI_API_KEY / OPENROUTER_API_KEY
    LLM_MODEL=...              # optional, overrides the default model

Use generate_answer() only when the adaptive engine decides ANSWER.
Any failure returns the retrieved lines as a fallback answer instead of
crashing the API. Never put API keys in code or in chat.js.
"""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided context. "
    "If the context does not contain the answer, say you do not have "
    "reliable information. Keep the answer short and clear."
)

# Model names change often. If a model is rejected, check the provider's
# console for the current name and set LLM_MODEL in .env.
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "model": "openai/gpt-oss-120b",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-2.5-flash",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "model": "google/gemma-4-31b-it:free",
    },
}


def _fallback(context_lines, reason, provider=None):
    return {
        "answer": " ".join(context_lines) if context_lines else "",
        "mode": "fallback",
        "provider": provider,
        "model_id": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "error": reason,
    }


def _bedrock(question, context_lines, max_tokens):
    try:
        from .bedrock_client import generate_answer as bedrock_answer
    except ImportError:
        from bedrock_client import generate_answer as bedrock_answer
    result = bedrock_answer(question, context_lines, max_tokens)
    result["provider"] = "bedrock"
    return result


def generate_answer(question, context_lines, max_tokens=500):
    provider = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider == "bedrock":
        return _bedrock(question, context_lines, max_tokens)

    cfg = PROVIDERS.get(provider)
    if cfg is None:
        return _fallback(context_lines, f"Unknown LLM_PROVIDER: {provider}")

    api_key = os.getenv(cfg["key_env"])
    if not api_key:
        return _fallback(context_lines, f"{cfg['key_env']} is not set", provider)

    model = os.getenv("LLM_MODEL", cfg["model"])
    context = "\n".join(f"- {line}" for line in context_lines)
    prompt = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        from openai import OpenAI

        client = OpenAI(base_url=cfg["base_url"], api_key=api_key, timeout=30)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return _fallback(context_lines, "Empty response from model", provider)
        usage = getattr(resp, "usage", None)
        return {
            "answer": text,
            "mode": "llm",
            "provider": provider,
            "model_id": model,
            "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "error": None,
        }
    except ImportError:
        return _fallback(context_lines, "Run: pip install openai", provider)
    except Exception as e:  # network, auth, rate limit, bad model name
        return _fallback(context_lines, f"{type(e).__name__}: {e}", provider)


if __name__ == "__main__":
    lines = ["Library hours: Monday to Saturday, 9 AM to 6 PM."]
    result = generate_answer("When does the library open?", lines)
    for key, value in result.items():
        print(f"{key}: {value}")