# core/summarize/map_reduce.py

from typing import List, Dict, Optional
import re, textwrap
from aifinreport.llm.client import complete

# Default tolerance for target length (±10%)
LENGTH_TOLERANCE = 0.10


def split_paragraphs(text: str) -> List[str]:
    """Split text on blank lines, keep substantial paragraphs."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip())]
    return [p for p in paras if len(p) > 60]


def group_paragraphs(paras: List[str], max_chars: int = 1800) -> List[str]:
    """Group paragraphs into chunks without exceeding max_chars."""
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

TARGET LENGTH: approximately {target_chars} characters
ACCEPTABLE RANGE: {min_chars}-{max_chars} characters

Use the consolidated bullets below as your only source of truth. 

PRIORITIES:
1. Financial metrics (revenue, earnings, EPS, margins, guidance)
2. Key business drivers (deliveries/production for TSLA, datacenter/GPU for NVDA)
3. Material risks or opportunities
4. Strategic developments

Write in clear prose (not bullet points). Prioritize completeness over brevity - if critical 
investment information requires slightly exceeding {max_chars} characters, that's acceptable.
Quality and accuracy matter more than hitting an exact character count.

Consolidated bullets:
{bullets}
"""


def map_article_to_bullets(body: str, ticker: str) -> List[str]:
    """
    Map a single article body to key bullet points.
    
    Args:
        body: Full article text
        ticker: Stock ticker symbol
    
    Returns:
        List of bullet points (max 12)
    """
    paras = split_paragraphs(body or "")
    if not paras:
        return []
    
    chunks = group_paragraphs(paras, max_chars=1800)
    all_bullets: List[str] = []
    
    for ch in chunks:
        prompt = MAP_PROMPT_TMPL.format(ticker=ticker, chunk=ch)
        out = complete(prompt)
        
        # Collect lines that look like bullets
        lines = [l.strip(" -•\t") for l in out.splitlines() if l.strip()]
        bullets = [l for l in lines if len(l) > 3]
        all_bullets.extend(bullets)
    
    # Simple deduplication
    seen, uniq = set(), []
    for b in all_bullets:
        k = re.sub(r"\W+", " ", b.lower()).strip()
        if k not in seen:
            seen.add(k)
            uniq.append(b)
    
    return uniq[:12]


def reduce_articles_to_bullets(per_article_bullets: List[List[str]], ticker: str) -> List[str]:
    """
    Reduce multiple articles' bullets into consolidated list.
    
    Args:
        per_article_bullets: List of bullet lists, one per article
        ticker: Stock ticker symbol
    
    Returns:
        Consolidated list of bullets (max 18)
    """
    flat = [b for lst in per_article_bullets for b in lst]
    if not flat:
        return []
    
    prompt = REDUCE_ARTICLE_TMPL.format(
        ticker=ticker,
        bullets="\n".join(f"- {b}" for b in flat)
    )
    out = complete(prompt)
    
    # Extract and deduplicate bullets
    lines = [l.strip(" -•\t") for l in out.splitlines() if l.strip()]
    uniq = []
    seen = set()
    
    for b in lines:
        k = re.sub(r"\W+", " ", b.lower()).strip()
        if k and k not in seen:
            seen.add(k)
            uniq.append(b)
    
    return uniq[:18]


def final_summary(
    ticker: str, 
    start: str, 
    end: str, 
    bullets: List[str],
    target_chars: int = 1800,
    min_chars: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> str:
    """
    Generate final investor summary from consolidated bullets.
    
    Uses soft guidance with target length and acceptable range (±10% by default).
    Does NOT hard-truncate to preserve completeness.
    
    Args:
        ticker: Stock ticker symbol
        start: Start date (YYYY-MM-DD)
        end: End date (YYYY-MM-DD)
        bullets: Consolidated bullet points
        target_chars: Target summary length (default: 1800)
        min_chars: Minimum acceptable length (default: 90% of target)
        max_chars: Maximum acceptable length (default: 110% of target)
    
    Returns:
        Generated summary text
    """
    # Calculate defaults if not provided (±10% tolerance)
    if min_chars is None:
        min_chars = int(target_chars * (1 - LENGTH_TOLERANCE))
    if max_chars is None:
        max_chars = int(target_chars * (1 + LENGTH_TOLERANCE))
    
    prompt = FINAL_SUMMARY_TMPL.format(
        ticker=ticker,
        start=start,
        end=end,
        target_chars=target_chars,
        min_chars=min_chars,
        max_chars=max_chars,
        bullets="\n".join(f"- {b}" for b in bullets)
    )
    
    out = complete(prompt)
    
    # SOFT GUIDANCE: Return as-is, trust the LLM
    # No hard truncation to avoid cutting mid-sentence
    return out.strip()