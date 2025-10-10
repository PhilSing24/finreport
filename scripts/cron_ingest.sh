#!/usr/bin/env bash
set -euo pipefail

cd /home/philippe/finreport
source /home/philippe/finreportenv/bin/activate

# 1) Ingest NVDA & TSLA for the last UTC business day (your script already does this)
python -m scripts.ingest_nvda_tsla

# 2) Lightweight dedup AFTER ingestion

# A) Dedup by exact URL (keep one row per URL)
psql -d finreport -v ON_ERROR_STOP=1 -c "
DELETE FROM news_raw a
USING news_raw b
WHERE a.ctid < b.ctid
  AND a.article_url = b.article_url;
"

# B) Dedup by (title, tickers) — catches syndication with different URLs
psql -d finreport -v ON_ERROR_STOP=1 -c "
DELETE FROM news_raw a
USING news_raw b
WHERE a.ctid < b.ctid
  AND a.title = b.title
  AND a.tickers = b.tickers;
"

deactivate
