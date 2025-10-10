# scripts/make_ticker_period_summary.py

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

from core.selectors.select_finance_yahoo import select_articles
from core.summarize.map_reduce import (
    map_article_to_bullets,
    reduce_articles_to_bullets,
    final_summary,
)

# --- env / paths ---
load_dotenv(Path.home() / "finreport" / ".env")
BUILD_DIR = Path.home() / "finreport" / "build"
BUILD_DIR.mkdir(parents=True, exist_ok=True)


def run(ticker: str, start: str, end: str, max_articles: int, max_summary_chars: int, min_body_chars: int):
    # 1) Select candidate articles (already filtered to finance.yahoo.com in the selector)
    rows = select_articles(
        ticker,
        start,
        end,
        max_articles=max_articles,
        min_body_chars=min_body_chars,
    )

    # 2) Map: per-article bullets
    per_article_bullets = []
    for r in rows:
        body = r.get("full_body") or ""
        if not body:
            continue
        bullets = map_article_to_bullets(body, ticker)
        if bullets:
            per_article_bullets.append(bullets)

    # 3) Reduce: consolidate bullets across articles
    consolidated = reduce_articles_to_bullets(per_article_bullets, ticker)

    # 4) Final: compose a compact investor-style summary
    summary_text = final_summary(
        ticker,
        start,
        end,
        consolidated,
        max_chars=max_summary_chars,
    ).strip()

    # If LLM returned nothing for some reason, fall back to a terse synthesis
    if not summary_text:
        if consolidated:
            summary_text = " • ".join(consolidated)[:max_summary_chars]
        else:
            summary_text = f"No finance-relevant news selected for {ticker} in [{start} → {end})."

    # 5) Render Markdown
    urls = [r.get("url") for r in rows if r.get("url")]
    sources_md = "\n".join(f"- {u}" for u in urls) if urls else "- No relevant sources found."

    md = (
        f"# Ticker: {ticker}\n"
        f"**Period:** [{start} → {end}]\n\n"
        f"---\n\n"
        f"## Summary\n\n"
        f"**{ticker} Investor Summary — {end}**\n\n"
        f"{summary_text}\n\n"
        f"*({len(summary_text)} characters)*\n\n"
        f"---\n\n"
        f"## Sources\n"
        f"{sources_md}\n"
    )

    out_path = BUILD_DIR / f"summary_{ticker}_{start}_{end}.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"✅ Wrote {out_path}")
    print(f"Selected articles: {len(rows)}  |  Consolidated bullets: {len(consolidated)}")


def main():
    p = argparse.ArgumentParser(description="Generate a ticker summary over a period.")
    p.add_argument("start", help="YYYY-MM-DD (inclusive)")
    p.add_argument("end", help="YYYY-MM-DD (exclusive)")
    p.add_argument("--ticker", default="NVDA", help="Ticker symbol, e.g. NVDA or TSLA")
    p.add_argument("--max-articles", type=int, default=12)
    p.add_argument("--min-body-chars", type=int, default=800)
    p.add_argument("--max-summary-chars", type=int, default=1800)
    args = p.parse_args()

    run(
        args.ticker.upper(),
        args.start,
        args.end,
        args.max_articles,
        args.max_summary_chars,
        args.min_body_chars,
    )


if __name__ == "__main__":
    main()

