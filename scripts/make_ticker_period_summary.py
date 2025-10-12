# scripts/make_ticker_period_summary.py

import os                               # Import the operating system interface module for environment variable access
import sys                              # Import system-specific parameters and functions (used for sys.argv for command-line args)
import argparse                         # Import argument parser for creating user-friendly command-line interfaces
from pathlib import Path                # Import Path class for object-oriented filesystem path handling (cross-platform)
from dotenv import load_dotenv          # Import function to load environment variables from .env file into os.environ

from core.selectors.select_finance_yahoo import select_articles    # Import the article selection function that filters and ranks Yahoo Finance articles
from core.summarize.map_reduce import (
    map_article_to_bullets,
    reduce_articles_to_bullets,
    final_summary,
)

# --- env / paths ---
load_dotenv(Path.home() / "finreport" / ".env")    # Load environment variables from .env file located in ~/finreport/.env
BUILD_DIR = Path.home() / "finreport" / "build"    # Define the output directory where generated Markdown summaries will be saved
BUILD_DIR.mkdir(parents=True, exist_ok=True)       # Create the build directory if it doesn't exist

# --- tolerance for target length (±10%) ---
LENGTH_TOLERANCE = 0.10


def run(ticker: str, start: str, end: str, max_articles: int, target_summary_chars: int, min_body_chars: int):
    # Calculate acceptable range for summary length (±10%)
    min_summary_chars = int(target_summary_chars * (1 - LENGTH_TOLERANCE))
    max_summary_chars = int(target_summary_chars * (1 + LENGTH_TOLERANCE))
    
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
        target_chars=target_summary_chars,
        min_chars=min_summary_chars,
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

    # Calculate how close we are to target
    actual_length = len(summary_text)
    length_status = "✓" if min_summary_chars <= actual_length <= max_summary_chars else "⚠"
    
    md = (
        f"# Ticker: {ticker}\n"
        f"**Period:** [{start} → {end}]\n\n"
        f"---\n\n"
        f"## Summary\n\n"
        f"**{ticker} Investor Summary — {end}**\n\n"
        f"{summary_text}\n\n"
        f"*({actual_length} characters {length_status} | target: {target_summary_chars} ±{int(LENGTH_TOLERANCE*100)}% [{min_summary_chars}-{max_summary_chars}])*\n\n"
        f"---\n\n"
        f"## Sources\n"
        f"{sources_md}\n"
    )

    out_path = BUILD_DIR / f"summary_{ticker}_{start}_{end}.md"
    out_path.write_text(md, encoding="utf-8")

    print(f"✅ Wrote {out_path}")
    print(f"Selected articles: {len(rows)}  |  Consolidated bullets: {len(consolidated)}")
    print(f"Summary length: {actual_length} chars (target: {target_summary_chars} ±{int(LENGTH_TOLERANCE*100)}% [{min_summary_chars}-{max_summary_chars}])")


def main():
    p = argparse.ArgumentParser(description="Generate a ticker summary over a period.")
    p.add_argument("start", help="YYYY-MM-DD (inclusive)")                                                 # positional argument start date
    p.add_argument("end", help="YYYY-MM-DD (exclusive)")                                                   # positional argument end date
    p.add_argument("--ticker", default="NVDA", help="Ticker symbol, e.g. NVDA or TSLA")                    # optional argument ticker
    p.add_argument("--max-articles", type=int, default=12, help="Maximum number of articles to select")
    p.add_argument("--min-body-chars", type=int, default=800, help="Minimum article body length")
    p.add_argument("--target-summary-chars", type=int, default=1800, 
                   help="Target summary length in characters (actual range will be ±10%%)")
    args = p.parse_args()

    run(
        args.ticker.upper(),
        args.start,
        args.end,
        args.max_articles,
        args.target_summary_chars,
        args.min_body_chars,
    )


if __name__ == "__main__":
    main()
    