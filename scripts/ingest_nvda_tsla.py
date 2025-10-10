# scripts/ingest_nvda_tsla.py
"""
Ingest NVDA & TSLA from Tiingo for a *complete* UTC day.
Usage:
  python -m scripts.ingest_nvda_tsla             # ingests *yesterday* UTC
  python -m scripts.ingest_nvda_tsla 2025-10-03  # explicit UTC day
"""
from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
import subprocess

TICKERS = ["NVDA", "TSLA"]

def yesterday_utc() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

def main():
    day = sys.argv[1] if len(sys.argv) > 1 else yesterday_utc()
    for tkr in TICKERS:
        print(f"\n=== Ingesting {tkr} for {day} (UTC) ===")
        res = subprocess.run(
            [sys.executable, "-m", "core.data.tiingo_news", day, tkr],
            capture_output=True, text=True
        )
        if res.stdout: print(res.stdout.strip())
        if res.stderr: print("stderr:", res.stderr.strip())

if __name__ == "__main__":
    main()
