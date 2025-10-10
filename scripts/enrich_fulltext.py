#!/usr/bin/env python3
from __future__ import annotations
import sys
from datetime import date, timedelta

from core.data.enrich_fulltext import enrich_range

def main(argv):
    """
    Usage:
      python -m scripts.enrich_fulltext               # yesterday UTC, both tickers
      python -m scripts.enrich_fulltext 2025-10-03    # that entire UTC day
      python -m scripts.enrich_fulltext 2025-10-01 2025-10-02 NVDA  # [start,end) + ticker
    """
    if len(argv) == 1:
        # default: yesterday UTC
        y = (date.today() - timedelta(days=1)).isoformat()
        start, end, tkr = y, (date.fromisoformat(y) + timedelta(days=1)).isoformat(), None
    elif len(argv) == 2:
        start = argv[1]
        end = (date.fromisoformat(start) + timedelta(days=1)).isoformat()
        tkr = None
    else:
        start = argv[1]
        end   = argv[2]
        tkr   = argv[3] if len(argv) >= 4 else None

    ok, fail, total = enrich_range(start, end, tkr, limit=None)
    print(f"[enrich_fulltext] range={start}..{end} ticker={tkr or '*'} -> ok={ok}, fail={fail}, total={total}")

if __name__ == "__main__":
    main(sys.argv)
