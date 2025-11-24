# src/aifinreport/tools/market_data_tools.py
"""
Market data tools for fetching stock prices.
Uses Massive.com API for OHLC data.
"""
import os
import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict

# ✅ Load .env early so os.getenv() can see the value
from dotenv import load_dotenv
load_dotenv()

# Get API key from environment
MASSIVE_API_KEY = os.getenv('MASSIVE_API_KEY')


def fetch_ohlc_bars(
    ticker: str,
    start_time: datetime,
    end_time: datetime,
    interval: str = "5min"
) -> List[Dict]:
    """
    Fetch OHLC bars from Massive.com API.
    
    Args:
        ticker: Stock symbol (e.g., 'NVDA')
        start_time: Start datetime (assumed UTC if no timezone)
        end_time: End datetime (assumed UTC if no timezone)
        interval: Bar interval - '1min', '5min', '15min', '1hour', '1day'
    
    Returns:
        List of OHLC bar dictionaries:
        [
            {
                "timestamp": datetime(...),
                "open": 125.50,
                "high": 126.20,
                "low": 125.30,
                "close": 125.80,
                "volume": 450000,
                "vwap": 125.75,       # optional
                "num_trades": 1250    # optional
            },
            ...
        ]
    
    Raises:
        ValueError: If API key missing or invalid parameters
        requests.HTTPError: If API request fails
    
    Example:
        >>> from datetime import datetime
        >>> start = datetime(2025, 8, 27, 20, 0, 0)
        >>> end = datetime(2025, 8, 28, 1, 0, 0)
        >>> bars = fetch_ohlc_bars("NVDA", start, end, "5min")
        >>> print(f"Got {len(bars)} bars")
    """
    if not MASSIVE_API_KEY:
        raise ValueError(
            "MASSIVE_API_KEY not found in environment. "
            "Add it to your .env file: MASSIVE_API_KEY=your_key"
        )
    
    # Parse interval (e.g., "5min" -> multiplier=5, timespan="minute")
    interval_map = {
        "1min": (1, "minute"),
        "5min": (5, "minute"),
        "15min": (15, "minute"),
        "30min": (30, "minute"),
        "1hour": (1, "hour"),
        "1day": (1, "day")
    }
    
    if interval not in interval_map:
        raise ValueError(
            f"Invalid interval: {interval}. "
            f"Must be one of {list(interval_map.keys())}"
        )
    
    multiplier, timespan = interval_map[interval]
    
    # CRITICAL FIX: Ensure times are treated as UTC
    # Without this, datetime.timestamp() uses local timezone (UTC+8 for Singapore)
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    # Format timestamps for API (using milliseconds for precision)
    from_ms = int(start_time.timestamp() * 1000)
    to_ms = int(end_time.timestamp() * 1000)
    
    # Build API URL
    url = (
        f"https://api.massive.com/v2/aggs/ticker/{ticker}/range/"
        f"{multiplier}/{timespan}/{from_ms}/{to_ms}"
    )
    
    # Make request
    headers = {
        "Authorization": f"Bearer {MASSIVE_API_KEY}"
    }
    
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle DELAYED status gracefully (future dates or data not yet available)
        if data.get('status') == 'DELAYED':
            return []  # Return empty list instead of raising error
        
        if data.get('status') != 'OK':
            raise requests.HTTPError(f"API returned status: {data.get('status')}")
        
        results = data.get('results', [])
        
        # Convert to our standard format
        bars = []
        for bar in results:
            bars.append({
                "timestamp": datetime.fromtimestamp(bar['t'] / 1000),  # Convert ms to datetime
                "open": bar['o'],
                "high": bar['h'],
                "low": bar['l'],
                "close": bar['c'],
                "volume": bar['v'],
                "vwap": bar.get('vw'),      # Volume weighted average price (optional)
                "num_trades": bar.get('n')  # Number of trades (optional)
            })
        
        return bars
    
    except requests.exceptions.RequestException as e:
        raise requests.HTTPError(f"Failed to fetch data from Massive.com: {e}")


def fetch_earnings_price_analysis(
    ticker: str,
    press_release_time: datetime,
    call_end_time: datetime
) -> dict:
    """
    Fetch three phases of price data around earnings event.
    
    Phase 1: Pre-event context (14 days before PR, daily bars)
    Phase 2: Event reaction (PR to call end, 5-min bars)
    Phase 3: Post-event follow-through (7 days after call, daily bars)
    
    Args:
        ticker: Stock symbol (e.g., 'NVDA')
        press_release_time: When press release was published (UTC)
        call_end_time: When earnings call ended (UTC)
    
    Returns:
        {
            'pre_event': [...],      # 14 daily bars before PR
            'event': [...],          # 5-min bars during PR/call
            'post_event': [...],     # 7 daily bars after call
            'summary': {
                'pre_bars': int,
                'event_bars': int,
                'post_bars': int,
                'total_bars': int
            }
        }
    
    Example:
        >>> pr_time = datetime(2025, 11, 19, 21, 30, 0)
        >>> call_end = datetime(2025, 11, 19, 23, 4, 0)
        >>> prices = fetch_earnings_price_analysis("NVDA", pr_time, call_end)
        >>> print(f"Pre-event: {len(prices['pre_event'])} bars")
        >>> print(f"Event: {len(prices['event'])} bars")
        >>> print(f"Post-event: {len(prices['post_event'])} bars")
    """
    print(f"\n📊 Fetching 3-phase price analysis for {ticker}")
    print(f"   PR time: {press_release_time}")
    print(f"   Call end: {call_end_time}")
    
    # Phase 1: Pre-event context (14 days before PR, daily)
    print("\n   Phase 1: Pre-event context (14 days, daily bars)...")
    pre_start = press_release_time - timedelta(days=14)
    pre_bars = fetch_ohlc_bars(
        ticker=ticker,
        start_time=pre_start,
        end_time=press_release_time,
        interval="1day"
    )
    print(f"   ✅ {len(pre_bars)} daily bars")
    
    # Phase 2: Event reaction (PR to call end, 5-min)
    print("\n   Phase 2: Event reaction (PR to call end, 5-min bars)...")
    event_bars = fetch_ohlc_bars(
        ticker=ticker,
        start_time=press_release_time,
        end_time=call_end_time,
        interval="5min"
    )
    print(f"   ✅ {len(event_bars)} 5-minute bars")
    
    # Phase 3: Post-event follow-through (7 days after call, daily)
    print("\n   Phase 3: Post-event follow-through (7 days, daily bars)...")
    post_end = call_end_time + timedelta(days=7)
    
    # Don't fetch future dates or very recent dates (data might not be settled)
    today_utc = datetime.utcnow()
    two_days_ago = today_utc - timedelta(days=2)
    
    if post_end > two_days_ago:
        post_end = two_days_ago
        print(f"   ⚠️  Adjusted end to avoid delayed data: {post_end.date()}")
    
    post_bars = fetch_ohlc_bars(
        ticker=ticker,
        start_time=call_end_time,
        end_time=post_end,
        interval="1day"
    )
    print(f"   ✅ {len(post_bars)} daily bars")
    
    return {
        'pre_event': pre_bars,
        'event': event_bars,
        'post_event': post_bars,
        'summary': {
            'pre_bars': len(pre_bars),
            'event_bars': len(event_bars),
            'post_bars': len(post_bars),
            'total_bars': len(pre_bars) + len(event_bars) + len(post_bars),
            'pre_start': pre_start,
            'pre_end': press_release_time,
            'event_start': press_release_time,
            'event_end': call_end_time,
            'post_start': call_end_time,
            'post_end': post_end
        }
    }


if __name__ == "__main__":
    
    print("Testing market data tools...")
    print("=" * 70)
    
    # Test 1: Single fetch
    print("\n1️⃣  fetch_ohlc_bars() - Single window")
    print("-" * 70)
    call_time = datetime(2025, 8, 27, 21, 0, 0)
    
    try:
        bars = fetch_ohlc_bars(
            ticker="NVDA",
            start_time=call_time - timedelta(hours=1),
            end_time=call_time + timedelta(hours=3),
            interval="5min"
        )
        
        if bars:
            print(f"✅ Fetched {len(bars)} bars")
            print(f"   Price: ${bars[0]['close']:.2f} → ${bars[-1]['close']:.2f}")
            change = ((bars[-1]['close'] - bars[0]['close']) / bars[0]['close']) * 100
            print(f"   Change: {change:+.2f}%")
        else:
            print("⚠️  No bars returned")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Three-phase analysis
    print("\n2️⃣  fetch_earnings_price_analysis() - Three phases")
    print("-" * 70)
    
    pr_time = datetime(2025, 11, 19, 21, 30, 0)
    call_end = datetime(2025, 11, 19, 23, 4, 0)
    
    try:
        analysis = fetch_earnings_price_analysis(
            ticker="NVDA",
            press_release_time=pr_time,
            call_end_time=call_end
        )
        
        print("\n✅ Three-phase analysis complete!")
        print(f"\n   Summary:")
        print(f"   - Pre-event:  {analysis['summary']['pre_bars']} daily bars")
        print(f"   - Event:      {analysis['summary']['event_bars']} 5-min bars")
        print(f"   - Post-event: {analysis['summary']['post_bars']} daily bars")
        print(f"   - Total:      {analysis['summary']['total_bars']} bars")
        
        # Show price movements
        if analysis['pre_event']:
            pre_change = ((analysis['pre_event'][-1]['close'] - analysis['pre_event'][0]['close']) / 
                         analysis['pre_event'][0]['close']) * 100
            print(f"\n   Pre-event trend:  {pre_change:+.2f}%")
        
        if analysis['event']:
            event_change = ((analysis['event'][-1]['close'] - analysis['event'][0]['close']) / 
                           analysis['event'][0]['close']) * 100
            print(f"   Event reaction:   {event_change:+.2f}%")
        
        if analysis['post_event']:
            post_change = ((analysis['post_event'][-1]['close'] - analysis['post_event'][0]['close']) / 
                          analysis['post_event'][0]['close']) * 100
            print(f"   Post-event trend: {post_change:+.2f}%")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 70)
    print("🎉 Market data tools test complete!")