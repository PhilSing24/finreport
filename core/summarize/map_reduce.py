from typing import List, Dict
import re, textwrap
from core.llm.llm import complete

def split_paragraphs(text: str) -> List[str]:
    # split on blank lines, keep “substantial” paragraphs
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip())]
    return [p for p in paras if len(p) > 60]

def group_paragraphs(paras: List[str], max_chars=1800) -> List[str]:
    chunks, cur = [], []
    cur_len = 0
    for p in paras:
        if cur_len + len(p) + 2 > max_chars and cur:
            chunks.append("\n\n".join(cur))
            cur, cur_len = [], 0
        cur.append(p)
        cur_len += len(p) + 2
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks

MAP_PROMPT_TMPL = """You are an analyst. Extract 3-6 FACTUAL investor-relevant bullets from the text.
Focus on: figures (revenue, EPS, margins, deliveries), guidance/roadmap, product/tech, regulation/supply chain, risks.
Avoid fluff/opinion. If nothing relevant, return 1 short bullet stating 'No material investor updates'.

Ticker: {ticker}
Text:
\"\"\"
{chunk}
\"\"\"

Return bullets with hyphens, 1 line each, no numbering.
"""

REDUCE_ARTICLE_TMPL = """Deduplicate and condense the bullets below into 5-8 clean, non-overlapping, factual bullets for investors.
Keep numbers/units, tickers, and avoid repetition.

Ticker: {ticker}

Bullets:
{bullets}
"""

FINAL_SUMMARY_TMPL = """Write a concise investor summary for {ticker} covering {start} to {end}.
Use the consolidated bullets below as your only source of truth. Prioritize financials, guidance, deliveries/production (TSLA), datacenter/GPU (NVDA), and key risks.
Target length ≤ {max_chars} characters. Use clear prose (not bullets).

Consolidated bullets:
{bullets}
"""

def map_article_to_bullets(body: str, ticker: str) -> List[str]:
    paras = split_paragraphs(body or "")
    if not paras:
        return []
    chunks = group_paragraphs(paras, max_chars=1800)
    all_bullets: List[str] = []
    for ch in chunks:
        prompt = MAP_PROMPT_TMPL.format(ticker=ticker, chunk=ch)
        out = complete(prompt)
        # collect lines that look like bullets
        lines = [l.strip(" -•\t") for l in out.splitlines() if l.strip()]
        bullets = [l for l in lines if len(l) > 3]
        all_bullets.extend(bullets)
    # de-dupe simple
    seen, uniq = set(), []
    for b in all_bullets:
        k = re.sub(r"\W+", " ", b.lower()).strip()
        if k not in seen:
            seen.add(k); uniq.append(b)
    return uniq[:12]

def reduce_articles_to_bullets(per_article_bullets: List[List[str]], ticker: str) -> List[str]:
    flat = [b for lst in per_article_bullets for b in lst]
    if not flat:
        return []
    prompt = REDUCE_ARTICLE_TMPL.format(
        ticker=ticker,
        bullets="\n".join(f"- {b}" for b in flat)
    )
    out = complete(prompt)
    lines = [l.strip(" -•\t") for l in out.splitlines() if l.strip()]
    uniq = []
    seen = set()
    for b in lines:
        k = re.sub(r"\W+", " ", b.lower()).strip()
        if k and k not in seen:
            seen.add(k); uniq.append(b)
    return uniq[:18]

def final_summary(ticker: str, start: str, end: str, bullets: List[str], max_chars: int) -> str:
    prompt = FINAL_SUMMARY_TMPL.format(
        ticker=ticker, start=start, end=end, max_chars=max_chars,
        bullets="\n".join(f"- {b}" for b in bullets)
    )
    out = complete(prompt)
    # hard trim to max_chars in case model goes long
    return out.strip()[:max_chars]
