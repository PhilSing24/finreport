from aifinreport.config import LLM_PROVIDER, MISTRAL_API_KEY, OPENAI_API_KEY, LLM_MODEL, LLM_MISTRAL_FALLBACKS
# core/llm/llm.py
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



# preferred models



def _complete_mistral(prompt: str, model: str, max_retries=4, base_sleep=1.0) -> Optional[str]:
    if not (Mistral and MISTRAL_API_KEY):
        return None
    client = Mistral(api_key=MISTRAL_API_KEY)

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
    if not (OPENAI_API_KEY and OpenAIClient):
        return None
    client = OpenAIClient(api_key=OPENAI_API_KEY)
    resp = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    # SDK exposes concatenated text via output_text
    return getattr(resp, "output_text", None)


def complete(prompt: str) -> str:
    """
    Best-effort completion with retries and fallbacks:
      1) If LLM_PROVIDER=mistral: try primary model w/ retries, then Mistral fallbacks.
      2) If that fails and OPENAI is available, try OpenAI.
      3) If LLM_PROVIDER=openai: go straight to OpenAI.
    """
    if LLM_PROVIDER == "mistral":
        # try primary
        out = _complete_mistral(prompt, LLM_MODEL)
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

    elif LLM_PROVIDER == "openai":
        out = _complete_openai(prompt)
        if out:
            return out
        # optional: try mistral as fallback if configured
        out = _complete_mistral(prompt, LLM_MODEL)
        if out:
            return out
        raise RuntimeError("OpenAI failed and no working Mistral fallback available.")

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER}")
