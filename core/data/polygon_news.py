# core/data/polygon_news.py
from __future__ import annotations
import os, time, datetime as dt
from typing import Iterable, Optional, Dict, Any, List
from pathlib import Path

import httpx
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

# --- env / config -----------------------------------------------------------
# Load .env from project root no matter where this module is run from
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

POLYGON_API_KEY = os.environ["POLYGON_API_KEY"]
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")
BASE = "https://api.polygon.io/v2/reference/news"

# --- helpers ----------------------------------------------------------------
def _iso_utc(dt_: dt.datetime) -> str:
    return dt_.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")

def _day_window_utc(day_str: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Return RFC3339 start/end for [day, day+1) in UTC, or (None,None) if day_str is None."""
    if not day_str:
        return None, None
    d = dt.date.fromisoformat(day_str)  # YYYY-MM-DD
    start = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
    end = start + dt.timedelta(days=1)
    return _iso_utc(start), _iso_utc(end)

# --- fetch ------------------------------------------------------------------
def fetch_news(
    ticker: Optional[str] = None,
    published_utc: Optional[str] = None,  # YYYY-MM-DD (UTC day) or None
    limit: int = 1000,
) -> Iterable[Dict[str, Any]]:
    """
    Stream Polygon news objects.
    - If ticker is None -> general mixed feed
    - If published_utc is 'YYYY-MM-DD' -> strict UTC-day window via .gte/.lt
    - Follows next_url until exhausted
    """
    start_iso, end_iso = _day_window_utc(published_utc)
    params: Dict[str, Any] = {
        "order": "asc",
        "sort": "published_utc",
        "limit": limit,
    }
    if ticker:
        params["ticker"] = ticker
    if start_iso and end_iso:
        params["published_utc.gte"] = start_iso
        params["published_utc.lt"] = end_iso

    headers = {"Authorization": f"Bearer {POLYGON_API_KEY}"}
    url = BASE
    with httpx.Client(timeout=60) as client:
        first = True
        while url:
            r = client.get(url, params=params if first else None, headers=headers)
            r.raise_for_status()
            data = r.json()
            for item in data.get("results") or []:
                yield item
            url = data.get("next_url")
            first = False
            if url:
                time.sleep(0.2)

# --- upsert -----------------------------------------------------------------
def upsert_news(items: Iterable[Dict[str, Any]]) -> int:
    """
    Upsert into news_raw. Wrap JSON(L) fields so psycopg2 can adapt properly.
    """
    rows: List[tuple] = []
    for x in items:
        rows.append((
            x["id"],
            x.get("published_utc"),
            x.get("title"),
            x.get("article_url"),
            x.get("description"),
            x.get("image_url"),
            Json(x.get("publisher")),   # JSONB
            x.get("tickers"),           # TEXT[]
            x.get("keywords"),          # TEXT[]
            Json(x.get("insights")),    # JSONB
        ))
    if not rows:
        return 0

    sql = """
    INSERT INTO news_raw
      (id, published_utc, title, article_url, description, image_url,
       publisher, tickers, keywords, insights)
    VALUES %s
    ON CONFLICT (id) DO UPDATE SET
      published_utc = EXCLUDED.published_utc,
      title         = EXCLUDED.title,
      article_url   = EXCLUDED.article_url,
      description   = EXCLUDED.description,
      image_url     = EXCLUDED.image_url,
      publisher     = EXCLUDED.publisher,
      tickers       = EXCLUDED.tickers,
      keywords      = EXCLUDED.keywords,
      insights      = EXCLUDED.insights;
    """
    with psycopg2.connect(PG_DSN) as conn, conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
        return len(rows)

# --- CLI --------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        # default demo: today's AAPL (UTC)
        day = dt.datetime.utcnow().strftime("%Y-%m-%d")
        tkr = "AAPL"
    elif len(sys.argv) == 2:
        # date only -> general feed for that UTC day
        day = sys.argv[1]
        tkr = None
    else:
        # date + ticker
        day = sys.argv[1]
        tkr = sys.argv[2] or None

    count = upsert_news(fetch_news(ticker=tkr, published_utc=day))
    print(f"upserted: {count}")
