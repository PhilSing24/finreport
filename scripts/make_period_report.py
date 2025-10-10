# scripts/make_period_report.py
import os, sys, argparse, textwrap
from pathlib import Path
from datetime import datetime
from sqlalchemy import text, bindparam
from core.data.db import engine
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path.home() / "finreport" / ".env")

def fetch_articles(start: str, end: str, tickers=None, source=None) -> pd.DataFrame:
    """
    Fetch articles between [start, end) optionally filtered by tickers and source.
    start, end are 'YYYY-MM-DD' strings.
    """
    where = [
        "published_date_utc >= :start",
        "published_date_utc <  :end",
    ]

    params = {"start": start, "end": end}

    if source:
        where.append("publisher->>'name' = :source")
        params["source"] = source

    stmt_txt = f"""
        SELECT
            id,
            published_utc,
            published_date_utc,
            title,
            article_url AS url,
            publisher->>'name' AS source,
            tickers,
            description,
            summary,
            full_body_chars
        FROM news_raw
        WHERE {" AND ".join(where)}
    """

    # Add ticker filter if provided
    if tickers:
        stmt_txt += """
          AND EXISTS (
                SELECT 1 FROM unnest(tickers) t
                WHERE t IN :tickers
          )
        """

    stmt_txt += " ORDER BY published_utc;"

    stmt = text(stmt_txt)

    # VERY IMPORTANT: expanding bind for IN (:tickers)
    if tickers:
        # ensure it's a tuple/list; expanding requires a sequence
        if isinstance(tickers, str):
            tickers = [tickers]
        params["tickers"] = tuple(tickers)
        stmt = stmt.bindparams(bindparam("tickers", expanding=True))

    with engine.connect() as conn:
        return pd.read_sql(stmt, conn, params=params)

def render_markdown(df: pd.DataFrame, start: str, end: str, tickers=None, source=None) -> str:
    period = f"{start} → {end}"
    tickers_label = ", ".join(tickers) if tickers else "NVDA, TSLA"
    source_label = source or "all sources"
    header = textwrap.dedent(f"""
    # Weekly News Summary
    **Period (UTC):** {period}  
    **Tickers:** {tickers_label}  
    **Source filter:** {source_label}  
    **Articles:** {len(df)}
    ---
    """).strip()

    lines = [header, ""]
    for _, r in df.iterrows():
        tks = ",".join(r.get("tickers", []) or [])
        summary = (r.get("summary") or "").strip()
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        src = (r.get("source") or "").strip()
        when = r.get("published_utc")
        when_s = when.strftime("%Y-%m-%d %H:%M UTC") if hasattr(when, "strftime") else str(when)

        lines.append(f"### {title}")
        lines.append(f"- **When:** {when_s}")
        lines.append(f"- **Source:** {src}")
        lines.append(f"- **Tickers:** {tks}")
        lines.append(f"- **Link:** {url}")
        if summary:
            lines.append("")
            lines.append(summary)
        lines.append("\n---\n")

    return "\n".join(lines)

def save_markdown(md: str, start: str, end: str, tickers=None, source=None) -> str:
    tickers_part = "_".join(tickers) if tickers else "NVDA_TSLA"
    src_part = (source or "all").replace(".", "-")
    out_dir = Path("build")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"weekly_{tickers_part}_{src_part}_{start}_{end}.md"
    out_path.write_text(md, encoding="utf-8")
    return str(out_path)

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("start_date", help="UTC start date (YYYY-MM-DD, inclusive)")
    ap.add_argument("end_date", help="UTC end date (YYYY-MM-DD, exclusive)")
    ap.add_argument("--tickers", nargs="+", help="One or more tickers (space-separated), e.g. --tickers NVDA TSLA")
    ap.add_argument("--source", help="Exact publisher domain match, e.g. finance.yahoo.com")
    args = ap.parse_args(argv[1:])

    start = args.start_date
    end = args.end_date
    tickers = args.tickers
    source = args.source

    df = fetch_articles(start, end, tickers, source)
    md = render_markdown(df, start, end, tickers, source)
    path = save_markdown(md, start, end, tickers, source)
    print(f"✅ Wrote {path}")
    print(f"Fetched rows: {len(df)} (tickers={tickers if tickers else ['NVDA','TSLA']}, source={source or 'all'})")

if __name__ == "__main__":
    main(sys.argv)
