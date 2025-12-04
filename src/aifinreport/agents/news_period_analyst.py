# src/aifinreport/agents/news_period_analyst.py
"""
News Period Analyst - Analyze news and stock performance for any time period
"""
from datetime import datetime, timezone as tz
from typing import Dict, List
from aifinreport.tools.database_tools import search_news
from aifinreport.tools.market_data_tools import fetch_ohlc_bars
from aifinreport.agents.news_ranker import (
    rank_articles_by_relevance,
    print_ranked_articles
)


def calculate_return(bars: List[Dict]) -> float:
    """Calculate total return from price bars."""
    if not bars or len(bars) < 2:
        return 0.0
    
    start_price = bars[0]['close']
    end_price = bars[-1]['close']
    
    return (end_price - start_price) / start_price


def analyze_news_period(
    ticker: str,
    start_date: datetime,
    end_date: datetime,
    quarter: str = None,
    top_n_articles: int = 10,
    context: str = None
) -> Dict:
    """
    Analyze news coverage and stock performance for a specific time period.
    
    Args:
        ticker: Stock ticker (e.g., "NVDA")
        start_date: Start of analysis period
        end_date: End of analysis period
        quarter: Optional quarter label for relevance ranking (e.g., "Q3")
        top_n_articles: Number of most relevant articles to analyze (default: 10)
        context: Optional description of what this period represents
    
    Returns:
        Analysis results with ranked news and stock performance
    
    Example:
        >>> from datetime import datetime, timedelta, timezone
        >>> # Pre-earnings analysis (7 days before PR)
        >>> pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=timezone.utc)
        >>> result = analyze_news_period(
        ...     ticker="NVDA",
        ...     start_date=pr_time - timedelta(days=7),
        ...     end_date=pr_time,
        ...     quarter="Q3",
        ...     context="Pre-earnings expectations"
        ... )
    """
    print("=" * 70)
    print("📊 NEWS PERIOD ANALYSIS")
    print("=" * 70)
    
    # Convert to UTC for display
    if start_date.tzinfo:
        start_utc = start_date.astimezone(tz.utc).replace(tzinfo=None)
    else:
        start_utc = start_date
        
    if end_date.tzinfo:
        end_utc = end_date.astimezone(tz.utc).replace(tzinfo=None)
    else:
        end_utc = end_date
    
    print(f"\nTicker: {ticker}")
    if quarter:
        print(f"Quarter: {quarter}")
    if context:
        print(f"Context: {context}")
    
    print(f"\nPeriod: {start_utc.date()} → {end_utc.date()}")
    
    # Calculate period length
    period_days = (end_date - start_date).days
    print(f"Duration: {period_days} days")
    
    # Get news
    print(f"\n📰 Fetching news articles...")
    all_news = search_news(
        ticker=ticker,
        start_time=start_date,
        end_time=end_date
    )
    print(f"   Found {len(all_news)} total articles")
    
    if len(all_news) == 0:
        print("\n⚠️  No articles found for this period")
        return {
            'ticker': ticker,
            'quarter': quarter,
            'start_date': start_utc,
            'end_date': end_utc,
            'period_days': period_days,
            'context': context,
            'total_news_count': 0,
            'selected_news_count': 0,
            'ranked_news': [],
            'all_news': [],
            'price_bars': 0,
            'stock_return': 0.0,
            'bars': []
        }
    
    # Rank by semantic relevance
    print(f"\n🔍 Ranking articles by relevance using local embeddings...")
    ranked_news = rank_articles_by_relevance(
        all_news,
        ticker=ticker,
        quarter=quarter or "earnings",
        top_n=top_n_articles
    )
    print(f"   Selected top {len(ranked_news)} most relevant articles")
    
    # Print ranked articles
    print_ranked_articles(ranked_news)
    
    # Get stock prices
    print(f"\n📈 Fetching stock prices...")
    bars = fetch_ohlc_bars(
        ticker,
        start_date,
        end_date,
        "1day"
    )
    print(f"   Fetched {len(bars)} daily bars")
    
    # Calculate return
    stock_return = calculate_return(bars)
    
    print(f"\n💹 Stock Performance:")
    print(f"   {ticker}: {stock_return*100:+.2f}%")
    
    if bars:
        print(f"   Start: ${bars[0]['close']:.2f} ({bars[0]['timestamp'].date()})")
        print(f"   End:   ${bars[-1]['close']:.2f} ({bars[-1]['timestamp'].date()})")
        print(f"   Range: ${min(b['low'] for b in bars):.2f} - ${max(b['high'] for b in bars):.2f}")
    
    print("\n" + "=" * 70)
    
    return {
        'ticker': ticker,
        'quarter': quarter,
        'start_date': start_utc,
        'end_date': end_utc,
        'period_days': period_days,
        'context': context,
        'total_news_count': len(all_news),
        'selected_news_count': len(ranked_news),
        'price_bars': len(bars),
        'stock_return': stock_return,
        'bars': bars,
        'ranked_news': ranked_news,
        'all_news': all_news
    }


if __name__ == "__main__":
    from datetime import timedelta
    
    # Example: Pre-earnings analysis for NVDA Q3
    # 7 days before press release (Nov 19, 2025 21:30 UTC)
    pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=tz.utc)
    
    result = analyze_news_period(
        ticker="NVDA",
        start_date=pr_time - timedelta(days=7),
        end_date=pr_time,
        quarter="Q3",
        top_n_articles=10,
        context="Pre-earnings expectations (7 days before press release)"
    )
    
    print(f"\n✅ Analysis complete!")
    print(f"   Analyzed {result['total_news_count']} articles")
    print(f"   Selected {result['selected_news_count']} most relevant")
    print(f"   Stock return: {result['stock_return']*100:+.2f}%")