import os, time
from typing import Optional

# --- Mistral ---
try:
    from mistralai import Mistral
    from mistralai.models.sdkerror import SDKError as MistralSDKError
except Exception:
    Mistral = None
    MistralSDKError = Exception

# --- OpenAI ---
try:
    from openai import OpenAI as OpenAIClient
except Exception:
    OpenAIClient = None


PROVIDER = os.getenv("LLM_PROVIDER", "mistral").lower()
MISTRAL_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# preferred models
MISTRAL_PRIMARY = os.getenv("LLM_MODEL", "mistral-small-latest")
MISTRAL_FALLBACKS = [
    m.strip() for m in os.getenv(
        "LLM_MISTRAL_FALLBACKS",
        "mistral-medium-latest,mistral-large-latest"
    ).split(",") if m.strip()
]

OPENAI_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # used when PROVIDER=openai


def _complete_mistral(prompt: str, model: str, max_retries=4, base_sleep=1.0) -> Optional[str]:
    if not (Mistral and MISTRAL_KEY):
        return None
    client = Mistral(api_key=MISTRAL_KEY)

    for attempt in range(max_retries):
        try:
            resp = client.chat.complete(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content
        except MistralSDKError as e:
            # 429 or capacity error: backoff and retry
            msg = getattr(e, "message", str(e)) or ""
            if "429" in msg or "capacity" in msg.lower():
                time.sleep(base_sleep * (2 ** attempt))
                continue
            raise
    return None


def _complete_openai(prompt: str) -> Optional[str]:
    if not (OPENAI_KEY and OpenAIClient):
        return None
    client = OpenAIClient(api_key=OPENAI_KEY)
    resp = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    # SDK exposes concatenated text via output_text
    return getattr(resp, "output_text", None)


def complete(prompt: str) -> str:
    """
    Best-effort completion with retries and fallbacks:
      1) If PROVIDER=mistral: try primary model w/ retries, then Mistral fallbacks.
      2) If that fails and OPENAI is available, try OpenAI.
      3) If PROVIDER=openai: go straight to OpenAI.
    """
    if PROVIDER == "mistral":
        # try primary
        out = _complete_mistral(prompt, MISTRAL_PRIMARY)
        if out:
            return out
        # try fallbacks
        for m in MISTRAL_FALLBACKS:
            out = _complete_mistral(prompt, m)
            if out:
                return out
        # try OpenAI if available
        out = _complete_openai(prompt)
        if out:
            return out
        raise RuntimeError("All LLM backends failed (Mistral capacity + OpenAI unavailable).")

    elif PROVIDER == "openai":
        out = _complete_openai(prompt)
        if out:
            return out
        # optional: try mistral as fallback if configured
        out = _complete_mistral(prompt, MISTRAL_PRIMARY)
        if out:
            return out
        raise RuntimeError("OpenAI failed and no working Mistral fallback available.")

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")
