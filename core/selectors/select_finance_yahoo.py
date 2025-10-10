from typing import List, Dict, Sequence
import pandas as pd
from sqlalchemy import text
from core.data.db import engine

# --- finance signals (tweak as you wish) ---
UNIVERSAL = {
    "revenue", "eps", "guidance", "margin", "gross", "operating",
    "free cash flow", "datacenter", "data center", "gpu", "ai",
    "cloud", "capex", "opex", "supply", "demand", "backlog",
    "pricing", "valuation", "buyback", "dividend", "shipment",
    "china", "export",
}
NVDA_HINTS = UNIVERSAL | {"blackwell", "h100", "h200", "semiconductor"}
TSLA_HINTS = UNIVERSAL | {"delivery", "deliveries", "production", "fsd", "robotaxi", "autonomy", "cybertruck"}


def _hint_set(ticker: str) -> set:
    t = (ticker or "").upper()
    if t == "NVDA":
        return NVDA_HINTS
    if t == "TSLA":
        return TSLA_HINTS
    return UNIVERSAL


def _len_plateau(n: int, lo=500, hi=6000, peak=2500) -> float:
    """Score body length: 0 below lo, near-max around peak, tapering by hi."""
    if n is None:
        return 0.0
    n = int(n)
    if n <= lo:
        return 0.0
    if n >= hi:
        return 0.8
    # rise to peak
    x = min(n, peak) - lo
    denom = max(1, peak - lo)
    base = min(1.0, x / denom)
    # taper after peak
    if n > peak:
        tail = (hi - n) / max(1, (hi - peak))
        base = 0.8 + max(0.0, tail) * 0.2
    return float(base)


def _title_signal(title: str, hints: Sequence[str]) -> float:
    """Small signal for financially-relevant words in the title."""
    t = (title or "").lower()
    score = 0.0
    for k in [
        "guidance", "margin", "eps", "revenue", "delivery",
        "datacenter", "data center", "gpu", "fsd", "robotaxi",
        "china", " q1", " q2", " q3", " q4", "%",
    ]:
        if k in t:
            score += 0.025
    if any(h in t for h in hints):
        score += 0.05
    return min(score, 0.15)


def _keyword_overlap(keywords: Sequence[str], hints: Sequence[str]) -> float:
    """Overlap of extracted keywords with our hint set."""
    if not keywords:
        return 0.0
    # normalize in case DB returns keywords as a string
    if isinstance(keywords, str):
        ks = {k.strip().lower() for k in keywords.split(",") if k.strip()}
    else:
        ks = {str(k).lower() for k in keywords}
    hs = {h.lower() for h in hints}
    overlap = len(ks & hs)
    return overlap / (overlap + 4.0)  # gentle saturation


def score_row(row: Dict, ticker: str) -> float:
    """Combine summary length, keyword overlap, body length, and title signal."""
    hints = _hint_set(ticker)
    slen = len(row.get("summary") or "")
    summary_len_score = min(slen, 1200) / 1200.0
    kw_score = _keyword_overlap(row.get("keywords"), hints)
    body_chars = row.get("full_body_chars") or 0
    body_score = _len_plateau(body_chars)
    title_sc = _title_signal(row.get("title") or "", hints)
    score = 0.45 * summary_len_score + 0.30 * kw_score + 0.15 * body_score + 0.10 * title_sc
    return round(score, 6)


def _dedupe_keep_latest(df: pd.DataFrame) -> pd.DataFrame:
    """Dedupe by (lower(title), source) keeping the most recent row."""
    key = df["title"].fillna("").str.lower() + "||" + df["source"].fillna("")
    df = df.assign(_dupe_key=key)
    return (
        df.sort_values("published_utc")          # earliest first
          .drop_duplicates("_dupe_key", keep="last")  # keep latest
          .drop(columns=["_dupe_key"])
    )


def select_articles(
    ticker: str,
    start_date: str,
    end_date: str,
    max_articles: int = 12,
    min_body_chars: int = 800,
) -> List[Dict]:
    """
    Return ranked Yahoo Finance articles for a single ticker in [start_date, end_date).

    Rules:
    - Source: finance.yahoo.com
    - Ticker tagged on article
    - Parsed full_body present & long enough
    - Deduped by (title, source)
    - Ranked by composite score (summary length, keyword overlap, body length, title signal)
    """
    stmt = text("""
        SELECT
          id, published_utc, published_date_utc,
          title, article_url AS url,
          publisher->>'name' AS source,
          tickers, description, summary, keywords, full_body, full_body_chars
        FROM news_raw
        WHERE publisher->>'name' = 'finance.yahoo.com'
          AND :tkr = ANY(tickers)
          AND published_date_utc >= CAST(:start AS date)
          AND published_date_utc <  CAST(:end   AS date)
          AND fetch_status = 'ok'
          AND full_body IS NOT NULL
          AND full_body_chars >= :min_chars
        ORDER BY published_utc
    """)

    params = {
        "tkr": (ticker or "").upper(),
        "start": start_date,     # 'YYYY-MM-DD'
        "end": end_date,         # 'YYYY-MM-DD' (exclusive)
        "min_chars": int(min_body_chars),
    }

    with engine.connect() as conn:
        df = pd.read_sql(stmt, conn, params=params)

    if df.empty:
        return []

    # Normalize keywords to list for downstream safety
    if "keywords" in df.columns:
        def _norm_kw(v):
            if v is None:
                return []
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                return [k.strip() for k in v.split(",") if k.strip()]
            return list(v) if hasattr(v, "__iter__") else []
        df["keywords"] = df["keywords"].map(_norm_kw)

    df = _dedupe_keep_latest(df)

    # Score and pick top-N
    df["__score"] = df.apply(lambda r: score_row(r.to_dict(), ticker), axis=1)
    df = df.sort_values("__score", ascending=False)
    if max_articles is not None:
        df = df.head(int(max_articles))

    return df.drop(columns=["__score"]).to_dict(orient="records")
