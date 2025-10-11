# core/data/tiingo_news.py
"""
Fetch and validate news from Tiingo API, fetch full article bodies, 
generate summaries, then upsert to PostgreSQL.

Single-step ingestion: metadata + body + summary in one pass.
Schema aligned with Tiingo API field names.
"""
from __future__ import annotations
import os
import datetime as dt
import time
from pathlib import Path
from typing import Dict, Any, Iterable, Optional, List
import re

import httpx
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

from core.data.fetch_body_yahoo import fetch_article_text
from core.data.summarize_text import summarize_article

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

TIINGO_TOKEN = os.environ["TIINGO_API_TOKEN"]
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")
BASE = "https://api.tiingo.com/tiingo/news"

# Company name mappings for common tickers
TICKER_COMPANY_NAMES = {
    "NVDA": ["nvidia", "nvda"],
    "TSLA": ["tesla", "tsla"],
    "AAPL": ["apple", "aapl"],
    "MSFT": ["microsoft", "msft"],
    "GOOGL": ["google", "alphabet", "googl"],
    "AMZN": ["amazon", "amzn"],
    "META": ["meta", "facebook", "meta platforms"],
}


def _utc_window(day_iso: str) -> tuple[str, str]:
    """Convert a date to UTC window: [YYYY-MM-DD, YYYY-MM-DD+1)"""
    d = dt.date.fromisoformat(day_iso)
    return d.isoformat(), (d + dt.timedelta(days=1)).isoformat()


def _validate_ticker_relevance(
    article: Dict[str, Any],
    ticker: str,
    strict: bool = True
) -> tuple[bool, str]:
    """
    Validate that article is actually about the ticker, not just tagged by Tiingo.
    
    Checks:
    1. Ticker or company name in title (strongest signal)
    2. Ticker or company name in description
    3. Ticker in URL
    4. No conflicting ticker symbols in title (e.g., "(RUM)" when expecting NVDA)
    
    Args:
        article: Article dict from Tiingo API
        ticker: Expected ticker symbol (e.g., "NVDA")
        strict: If True, require explicit mention in content
    
    Returns:
        (is_valid, reason)
        - is_valid: True if article is about the ticker
        - reason: String explaining validation result
    """
    ticker_upper = ticker.upper()
    
    # Build search terms
    ticker_variations = {
        ticker_upper,
        ticker.lower(),
        f"${ticker_upper}",   # $NVDA
        f"({ticker_upper})",  # (NVDA)
    }
    
    # Add company names if known
    company_names = set(TICKER_COMPANY_NAMES.get(ticker_upper, []))
    search_terms = ticker_variations | company_names
    
    title = (article.get("title") or "").lower()
    description = (article.get("description") or "").lower()
    url = (article.get("url") or "").lower()
    
    # Check for conflicting ticker in title (e.g., "Rumble (RUM)" when expecting NVDA)
    found_tickers = re.findall(r'\(([A-Z]{2,5})\)', article.get("title") or "")
    if found_tickers and ticker_upper not in found_tickers:
        return False, f"title_mentions_different_ticker_{found_tickers[0]}"
    
    # Check 1: Title (most important)
    if any(term.lower() in title for term in search_terms):
        return True, "ticker_in_title"
    
    # Check 2: Description (good signal)
    if any(term.lower() in description for term in search_terms):
        return True, "ticker_in_description"
    
    # Check 3: URL (sometimes reliable)
    if ticker.lower() in url:
        return True, "ticker_in_url"
    
    # If strict mode and nothing found
    if strict:
        return False, f"no_mention_of_{ticker_upper}"
    
    # Non-strict: allow articles tagged by Tiingo even without text mention
    return True, "tiingo_tag_only"


def fetch_news(
    ticker: Optional[str],
    day_iso: str,
    limit: int = 1000,
    validate_content: bool = True,
    strict_validation: bool = True,
    fetch_bodies: bool = True,
    body_fetch_delay: float = 1.0,
) -> Iterable[Dict[str, Any]]:
    """
    Fetch news from Tiingo API for a specific ticker and date.
    Optionally fetch full article bodies and generate summaries.
    
    Args:
        ticker: Ticker symbol (e.g., "NVDA"), or None for all tickers
        day_iso: Date in YYYY-MM-DD format (UTC)
        limit: Max articles to fetch from API
        validate_content: If True, validate ticker appears in content
        strict_validation: If True, require explicit content mention
        fetch_bodies: If True, fetch full article bodies from URLs
        body_fetch_delay: Delay in seconds between body fetches (rate limiting)
    
    Yields:
        Normalized article dictionaries ready for database insertion
    """
    startDate, endDate = _utc_window(day_iso)
    params: Dict[str, Any] = {
        "startDate": startDate,
        "endDate": endDate,
        "limit": limit,
        "token": TIINGO_TOKEN,
    }
    if ticker:
        params["tickers"] = ticker.lower()

    # Statistics
    validation_rejected = 0
    validation_accepted = 0
    body_fetch_ok = 0
    body_fetch_failed = 0
    rejected_articles = []

    with httpx.Client(timeout=60) as client:
        r = client.get(BASE, params=params)
        r.raise_for_status()
        
        article_count = 0
        for x in (r.json() or []):
            # Normalize source + tickers (keep API field names)
            source_domain = (x.get("source") or "").strip().lower()
            tickers_raw = x.get("tickers") or []
            tickers = sorted({t.upper() for t in tickers_raw})

            # --- FILTER RULES ---
            # 1) Only Yahoo Finance
            if source_domain != "finance.yahoo.com":
                continue
            
            # 2) Only single-ticker articles that match requested ticker
            if ticker:
                if not (len(tickers) == 1 and tickers[0] == ticker.upper()):
                    continue
            else:
                # If no ticker specified, still require single-ticker
                if len(tickers) != 1:
                    continue

            # 3) CONTENT VALIDATION - verify ticker actually appears in content
            validation_status = "passed"
            validation_reason = "no_validation"
            
            if validate_content and ticker:
                is_valid, reason = _validate_ticker_relevance(
                    x, ticker, strict=strict_validation
                )
                validation_status = "passed" if is_valid else "failed"
                validation_reason = reason
                
                if not is_valid:
                    validation_rejected += 1
                    rejected_articles.append({
                        "title": x.get("title", "NO_TITLE")[:80],
                        "reason": reason,
                        "url": x.get("url", "NO_URL"),
                    })
                    continue
                
                validation_accepted += 1

            # 4) FETCH FULL BODY (if enabled)
            full_body = None
            full_body_chars = 0
            fetch_status = "not_fetched"
            body_extractor = None
            summary = None
            
            if fetch_bodies:
                article_url = x.get("url")
                if article_url:
                    # Rate limiting: delay between fetches
                    if article_count > 0:
                        time.sleep(body_fetch_delay)
                    
                    print(f"  Fetching body [{validation_accepted}]: {x.get('title', 'NO_TITLE')[:60]}...")
                    
                    full_body, extractor_or_error = fetch_article_text(article_url)
                    
                    if full_body:
                        # Success
                        full_body_chars = len(full_body)
                        fetch_status = "ok"
                        body_extractor = extractor_or_error
                        body_fetch_ok += 1
                        
                        # Generate summary
                        try:
                            summary = summarize_article(full_body, ticker or tickers[0])
                        except Exception as e:
                            print(f"    ⚠️  Summary generation failed: {e}")
                            summary = None
                        
                        print(f"    ✓ Body fetched: {full_body_chars} chars, extractor: {body_extractor}")
                    else:
                        # Failed
                        fetch_status = extractor_or_error or "unknown_error"
                        body_fetch_failed += 1
                        print(f"    ✗ Body fetch failed: {fetch_status}")

            # 5) Yield complete article record (API-aligned field names)
            yield {
                "id": f"tiingo:{x.get('id')}",
                "published_utc": x.get("publishedDate"),
                "crawl_date": x.get("crawlDate"),
                "title": x.get("title"),
                "url": x.get("url"),
                "description": x.get("description"),
                "source": source_domain,
                "tickers": tickers,
                "tags": x.get("tags") or [],
                "validation_status": validation_status,
                "validation_reason": validation_reason,
                "full_body": full_body,
                "full_body_chars": full_body_chars,
                "fetch_status": fetch_status,
                "body_extractor": body_extractor,
                "summary": summary,
            }
            
            article_count += 1
    
    # Print summary
    print(f"\n{'='*60}")
    print("INGESTION SUMMARY")
    print(f"{'='*60}")
    
    if validate_content:
        print(f"Content Validation:")
        print(f"  ✓ Accepted: {validation_accepted}")
        print(f"  ✗ Rejected: {validation_rejected}")
        
        if rejected_articles:
            print(f"\n  Rejected articles:")
            for art in rejected_articles[:5]:  # Show first 5
                print(f"    • [{art['reason']}] {art['title']}")
            if len(rejected_articles) > 5:
                print(f"    ... and {len(rejected_articles) - 5} more")
    
    if fetch_bodies:
        print(f"\nBody Fetching:")
        print(f"  ✓ Successful: {body_fetch_ok}")
        print(f"  ✗ Failed: {body_fetch_failed}")
        if body_fetch_ok + body_fetch_failed > 0:
            success_rate = body_fetch_ok / (body_fetch_ok + body_fetch_failed) * 100
            print(f"  Success rate: {success_rate:.1f}%")
    
    print(f"{'='*60}\n")


def upsert_news(items: Iterable[Dict[str, Any]]) -> int:
    """
    Upsert news articles into PostgreSQL database.
    Uses API-aligned field names.
    
    Args:
        items: Iterable of article dictionaries
    
    Returns:
        Number of rows upserted
    """
    rows: List[tuple] = []
    for x in items:
        if not x.get("id") or not x.get("published_utc"):
            continue
        rows.append((
            x["id"],
            x["published_utc"],
            x.get("crawl_date"),
            x.get("title"),
            x.get("url"),
            x.get("description"),
            x.get("source"),
            x.get("tickers"),
            x.get("tags"),
            x.get("validation_status"),
            x.get("validation_reason"),
            x.get("full_body"),
            x.get("full_body_chars"),
            x.get("fetch_status"),
            x.get("body_extractor"),
            x.get("summary"),
        ))
    
    if not rows:
        print("upserted: 0")
        return 0

    sql = """
    INSERT INTO news_raw
      (id, published_utc, crawl_date, title, url, description,
       source, tickers, tags, validation_status, validation_reason,
       full_body, full_body_chars, fetch_status, body_extractor, summary)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
      published_utc = EXCLUDED.published_utc,
      crawl_date    = EXCLUDED.crawl_date,
      title         = EXCLUDED.title,
      url           = EXCLUDED.url,
      description   = EXCLUDED.description,
      source        = EXCLUDED.source,
      tickers       = EXCLUDED.tickers,
      tags          = EXCLUDED.tags,
      validation_status = EXCLUDED.validation_status,
      validation_reason = EXCLUDED.validation_reason,
      full_body     = EXCLUDED.full_body,
      full_body_chars = EXCLUDED.full_body_chars,
      fetch_status  = EXCLUDED.fetch_status,
      body_extractor = EXCLUDED.body_extractor,
      summary       = EXCLUDED.summary;
    """
    
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
    
    print(f"upserted: {len(rows)}")
    return len(rows)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m core.data.tiingo_news YYYY-MM-DD TICKER [--no-bodies]")
        print("Example: python -m core.data.tiingo_news 2025-10-03 NVDA")
        print("         python -m core.data.tiingo_news 2025-10-03 NVDA --no-bodies")
        raise SystemExit(2)
    
    day, tkr = sys.argv[1], sys.argv[2]
    fetch_bodies = "--no-bodies" not in sys.argv
    
    print(f"Fetching {tkr} news for {day}...")
    print(f"Content validation: ON")
    print(f"Body fetching: {'ON' if fetch_bodies else 'OFF'}")
    print()
    
    upsert_news(fetch_news(
        tkr, 
        day, 
        validate_content=True, 
        strict_validation=True,
        fetch_bodies=fetch_bodies,
        body_fetch_delay=1.0,
    ))