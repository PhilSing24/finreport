# core/data/tiingo_news.py
from __future__ import annotations
import os, datetime as dt
from pathlib import Path
from typing import Dict, Any, Iterable, Optional, List

import httpx
import psycopg2
from psycopg2.extras import execute_values, Json
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

TIINGO_TOKEN = os.environ["TIINGO_API_TOKEN"]
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")
BASE = "https://api.tiingo.com/tiingo/news"

def _utc_window(day_iso: str) -> tuple[str, str]:
    d = dt.date.fromisoformat(day_iso)
    return d.isoformat(), (d + dt.timedelta(days=1)).isoformat()

def fetch_news(
    ticker: Optional[str],
    day_iso: str,
    limit: int = 1000,
) -> Iterable[Dict[str, Any]]:
    startDate, endDate = _utc_window(day_iso)
    params: Dict[str, Any] = {
        "startDate": startDate,
        "endDate": endDate,
        "limit": limit,
        "token": TIINGO_TOKEN,          # Tiingo expects token in query
    }
    if ticker:
        params["tickers"] = ticker.lower()

    with httpx.Client(timeout=60) as client:
        r = client.get(BASE, params=params)
        r.raise_for_status()
        for x in (r.json() or []):
            # normalize publisher + tickers
            publisher_domain = (x.get("source") or "").strip().lower()
            tickers_raw = x.get("tickers") or []
            tickers = sorted({t.upper() for t in tickers_raw})

            # --- FILTER RULES ---
            # 1) only Yahoo Finance
            if publisher_domain != "finance.yahoo.com":
                continue
            # 2) only unique single-ticker articles that match the requested ticker
            if ticker:
                if not (len(tickers) == 1 and tickers[0] == ticker.upper()):
                    continue
            else:
                # if no ticker provided, still require single-ticker article
                if len(tickers) != 1:
                    continue

            yield {
                "id": f"tiingo:{x.get('id')}",
                "published_utc": x.get("publishedDate"),
                "title": x.get("title"),
                "article_url": x.get("url"),
                "description": x.get("description"),
                "image_url": None,
                "publisher": {"name": publisher_domain},
                "tickers": tickers,
                "keywords": x.get("tags") or [],
                "insights": None,
            }

def upsert_news(items: Iterable[Dict[str, Any]]) -> int:
    rows: List[tuple] = []
    for x in items:
        if not x.get("id") or not x.get("published_utc"):
            continue
        rows.append((
            x["id"],
            x["published_utc"],
            x.get("title"),
            x.get("article_url"),
            x.get("description"),
            x.get("image_url"),
            Json(x.get("publisher")),
            x.get("tickers"),
            x.get("keywords"),
            Json(x.get("insights")),
        ))
    if not rows:
        print("upserted: 0")
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
    print(f"upserted: {len(rows)}")
    return len(rows)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m core.data.tiingo_news YYYY-MM-DD NVDA|TSLA")
        raise SystemExit(2)
    day, tkr = sys.argv[1], sys.argv[2]
    upsert_news(fetch_news(tkr, day))
