# scripts/validate_news_data.py
"""
Validation report for news_raw table.
Shows statistics on validation status and identifies potential data quality issues.

Usage:
  python -m scripts.validate_news_data
  python -m scripts.validate_news_data --detailed
  python -m scripts.validate_news_data --ticker NVDA
  python -m scripts.validate_news_data --failed-only
"""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd
from sqlalchemy import text
from core.data.db import engine


def validation_summary():
    """Show overall validation statistics."""
    query = text("""
        SELECT 
            validation_status,
            validation_reason,
            COUNT(*) as count
        FROM news_raw
        WHERE validation_status IS NOT NULL
        GROUP BY validation_status, validation_reason
        ORDER BY validation_status, count DESC
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    if df.empty:
        print("No validation data found. Run ingestion with validation enabled.")
        return
    
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)
    print(df.to_string(index=False))
    
    # Calculate pass rate
    total = df['count'].sum()
    passed = df[df['validation_status'] == 'passed']['count'].sum()
    failed = df[df['validation_status'] == 'failed']['count'].sum()
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{'='*80}")
    print(f"Pass Rate: {pass_rate:.1f}% ({passed:,}/{total:,})")
    print(f"Failed: {failed:,}")
    print(f"{'='*80}\n")


def validation_by_ticker():
    """Show validation statistics by ticker."""
    query = text("""
        SELECT 
            UNNEST(tickers) as ticker,
            validation_status,
            COUNT(*) as count
        FROM news_raw
        WHERE validation_status IS NOT NULL
        GROUP BY ticker, validation_status
        ORDER BY ticker, validation_status
    """)
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    
    if df.empty:
        print("No ticker validation data found.")
        return
    
    print("\n" + "="*80)
    print("VALIDATION BY TICKER")
    print("="*80)
    
    # Pivot for better readability
    pivot = df.pivot_table(
        index='ticker',
        columns='validation_status',
        values='count',
        fill_value=0,
        aggfunc='sum'
    )
    
    if 'passed' in pivot.columns and 'failed' in pivot.columns:
        pivot['pass_rate'] = (pivot['passed'] / (pivot['passed'] + pivot['failed']) * 100).round(1)
    
    print(pivot.to_string())
    print()


def failed_articles(ticker: str = None, limit: int = 20):
    """Show articles that failed validation."""
    params = {}
    where_clause = "WHERE validation_status = 'failed'"
    
    if ticker:
        where_clause += " AND :ticker = ANY(tickers)"
        params['ticker'] = ticker.upper()
    
    query = text(f"""
        SELECT 
            published_date_utc,
            tickers,
            title,
            validation_reason,
            article_url
        FROM news_raw
        {where_clause}
        ORDER BY published_date_utc DESC
        LIMIT :limit
    """)
    
    params['limit'] = limit
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    
    if df.empty:
        print(f"\nNo failed validations found" + (f" for {ticker}" if ticker else "") + ".")
        return
    
    print("\n" + "="*80)
    print(f"FAILED VALIDATIONS" + (f" FOR {ticker}" if ticker else ""))
    print("="*80)
    
    for _, row in df.iterrows():
        print(f"\nDate: {row['published_date_utc']}")
        print(f"Ticker(s): {', '.join(row['tickers'])}")
        print(f"Title: {row['title']}")
        print(f"Reason: {row['validation_reason']}")
        print(f"URL: {row['article_url']}")
        print("-" * 80)


def detailed_report(ticker: str = None):
    """Show detailed validation report."""
    validation_summary()
    validation_by_ticker()
    failed_articles(ticker=ticker, limit=10)


def main():
    parser = argparse.ArgumentParser(
        description="Validation report for news data quality."
    )
    
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show detailed report with failed articles"
    )
    
    parser.add_argument(
        "--ticker",
        type=str,
        help="Filter by specific ticker (e.g., NVDA)"
    )
    
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Show only failed validations"
    )
    
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max failed articles to show (default: 20)"
    )
    
    args = parser.parse_args()
    
    if args.failed_only:
        failed_articles(ticker=args.ticker, limit=args.limit)
    elif args.detailed:
        detailed_report(ticker=args.ticker)
    else:
        validation_summary()
        validation_by_ticker()


if __name__ == "__main__":
    main()