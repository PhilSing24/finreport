# scripts/ingest_tickers.py
"""
Ingest news for specified tickers from Tiingo for a complete UTC day.

Usage:
  python -m scripts.ingest_tickers                    # NVDA & TSLA for yesterday
  python -m scripts.ingest_tickers 2025-10-03         # NVDA & TSLA for specific day
  python -m scripts.ingest_tickers 2025-10-03 AAPL MSFT  # Custom tickers
  python -m scripts.ingest_tickers --yesterday AAPL   # Yesterday for AAPL only
"""
from __future__ import annotations
import sys
import argparse
from datetime import datetime, timedelta, timezone
import subprocess

# Default tickers to ingest
DEFAULT_TICKERS = ["NVDA", "TSLA"]


def yesterday_utc() -> str:
    """Get yesterday's date in UTC as ISO string."""
    return (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()


def main():
    parser = argparse.ArgumentParser(
        description="Ingest news from Tiingo for specified tickers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.ingest_tickers
    → Ingest NVDA & TSLA for yesterday (UTC)
  
  python -m scripts.ingest_tickers 2025-10-03
    → Ingest NVDA & TSLA for 2025-10-03
  
  python -m scripts.ingest_tickers 2025-10-03 AAPL MSFT GOOGL
    → Ingest AAPL, MSFT, GOOGL for 2025-10-03
  
  python -m scripts.ingest_tickers --yesterday AAPL
    → Ingest AAPL for yesterday
        """
    )
    
    parser.add_argument(
        "date",
        nargs="?",
        default=None,
        help="Date in YYYY-MM-DD format (UTC). Defaults to yesterday."
    )
    
    parser.add_argument(
        "tickers",
        nargs="*",
        help=f"Ticker symbols to ingest (default: {', '.join(DEFAULT_TICKERS)})"
    )
    
    parser.add_argument(
        "--yesterday",
        action="store_true",
        help="Explicitly use yesterday's date (UTC)"
    )
    
    args = parser.parse_args()
    
    # Determine date
    if args.yesterday:
        day = yesterday_utc()
    elif args.date:
        day = args.date
    else:
        day = yesterday_utc()
    
    # Determine tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = DEFAULT_TICKERS
    
    print(f"{'='*60}")
    print(f"Ingesting news for {day} (UTC)")
    print(f"Tickers: {', '.join(tickers)}")
    print(f"{'='*60}")
    
    # Ingest each ticker
    for tkr in tickers:
        print(f"\n{'='*60}")
        print(f"Processing {tkr}...")
        print(f"{'='*60}")
        
        res = subprocess.run(
            [sys.executable, "-m", "core.data.tiingo_news", day, tkr],
            capture_output=True,
            text=True
        )
        
        if res.stdout:
            print(res.stdout.strip())
        if res.stderr:
            print("STDERR:", res.stderr.strip())
        if res.returncode != 0:
            print(f"⚠️  Warning: Failed to ingest {tkr} (exit code: {res.returncode})")
    
    print(f"\n{'='*60}")
    print("Ingestion complete!")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()