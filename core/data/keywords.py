from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from core.data.finance_hints import FINANCE_HINTS

# Load once (module-global)
_embedder = SentenceTransformer("all-MiniLM-L6-v2")
_kw_model = KeyBERT(model=_embedder)

def _pretrim(text: str, max_chars: int = 3000) -> str:
    """Trim very long articles to keep keywording snappy."""
    t = (text or "").strip()
    return t[:max_chars] if len(t) > max_chars else t

def _postprocess(phrases, top_n: int):
    """Basic cleanup & dedupe while preserving order."""
    seen = set()
    cleaned = []
    for p, _score in phrases:
        k = p.strip().lower()
        if k and k not in seen:
            seen.add(k)
            cleaned.append(k)
        if len(cleaned) >= top_n:
            break
    return cleaned

def extract_keywords(text: str, ticker: str, top_n: int = 8):
    # 1) fast guard
    text = _pretrim(text)
    if not text:
        return []

    # 2) seed tokens
    tokens = FINANCE_HINTS.get(ticker, FINANCE_HINTS["*"])

    # 3) fast & diverse settings (MMR)
    phrases = _kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        stop_words='english',
        use_maxsum=False,     # avoid combinatorial blowups
        use_mmr=True,
        diversity=0.3,
        nr_candidates=20,
        top_n=max(top_n, 8),  # give postprocess room to dedupe
        seed_keywords=tokens
    )

    # 4) normalize & dedupe; return a LIST for Postgres text[]
    return _postprocess(phrases, top_n)
