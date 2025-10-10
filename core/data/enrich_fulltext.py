# core/data/enrich_fulltext.py
from __future__ import annotations
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import execute_batch
from dotenv import load_dotenv

from core.data.fetch_body_yahoo import fetch_article_text

# Load .env for PG_DSN if present
load_dotenv(Path.home() / "finreport" / ".env")
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")

def select_candidates(conn, start_date: str, end_date: str, ticker: Optional[str], limit: Optional[int]) -> Sequence[Tuple[str, str]]:
    sql = """
        SELECT id, article_url
        FROM news_raw
        WHERE publisher->>'name' = 'finance.yahoo.com'
          AND array_length(tickers,1) = 1
          AND published_date_utc >= %s::date
          AND published_date_utc <  %s::date
          AND (full_body IS NULL OR full_body = '')
        """
    params = [start_date, end_date]
    if ticker:
        sql += " AND %s = ANY(tickers)"
        params.append(ticker.upper())
    sql += " ORDER BY published_utc"
    if limit:
        sql += " LIMIT %s"
        params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()

def enrich_range(start_date: str, end_date: str, ticker: Optional[str] = None, limit: Optional[int] = None) -> Tuple[int, int, int]:
    """
    Enrich rows for [start_date, end_date) UTC, optional single ticker.
    Returns: (ok_count, fail_count, total)
    """
    now = datetime.now(timezone.utc)
    ok = fail = 0

    with psycopg2.connect(PG_DSN) as conn:
        rows = select_candidates(conn, start_date, end_date, ticker, limit)
        if not rows:
            return 0, 0, 0

        updates = []
        for (doc_id, url) in rows:
            text, status = fetch_article_text(url)
            if text:
                ok += 1
                updates.append((text, len(text), now, "ok", status, doc_id))
            else:
                fail += 1
                updates.append((None, None, now, status, None, doc_id))

        with conn.cursor() as cur:
            execute_batch(cur, """
                UPDATE news_raw
                   SET full_body       = %s,
                       full_body_chars = %s,
                       fetched_at      = %s,
                       fetch_status    = %s,
                       body_extractor  = %s
                 WHERE id = %s
            """, updates, page_size=200)

    return ok, fail, len(rows)
