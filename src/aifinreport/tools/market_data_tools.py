# src/aifinreport/tools/market_data_tools.py
"""
Market data tools for fetching stock prices.
Uses Massive.com API for OHLC data.
"""
import os
import requests
from datetime import datetime, timedelta
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
        start_time: Start datetime (UTC)
        end_time: End datetime (UTC)
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


if __name__ == "__main__":
    
    print("Testing fetch_ohlc_bars()...")
    print("=" * 70)
    
    # Test with NVDA Q2 FY2026 earnings call
    # Call was Aug 27, 2025 at 21:00 UTC (5:00 PM EDT)
    call_time = datetime(2025, 8, 27, 21, 0, 0)
    
    print(f"\nFetching NVDA 5-minute bars around earnings call")
    print(f"Call time: {call_time}")
    print(f"Window: 1 hour before to 3 hours after")
    
    try:
        bars = fetch_ohlc_bars(
            ticker="NVDA",
            start_time=call_time - timedelta(hours=1),
            end_time=call_time + timedelta(hours=3),
            interval="5min"
        )
        
        print(f"\n✅ Successfully fetched {len(bars)} bars")
        
        if bars:
            print(f"\nFirst bar:")
            first = bars[0]
            print(f"  Time:   {first['timestamp']}")
            print(f"  Open:   ${first['open']:.2f}")
            print(f"  High:   ${first['high']:.2f}")
            print(f"  Low:    ${first['low']:.2f}")
            print(f"  Close:  ${first['close']:.2f}")
            print(f"  Volume: {first['volume']:,}")
            
            print(f"\nLast bar:")
            last = bars[-1]
            print(f"  Time:   {last['timestamp']}")
            print(f"  Open:   ${last['open']:.2f}")
            print(f"  High:   ${last['high']:.2f}")
            print(f"  Low:    ${last['low']:.2f}")
            print(f"  Close:  ${last['close']:.2f}")
            print(f"  Volume: {last['volume']:,}")
            
            # Show price movement
            price_change = last['close'] - first['close']
            price_change_pct = (price_change / first['close']) * 100
            print(f"\nPrice movement:")
            print(f"  Start: ${first['close']:.2f}")
            print(f"  End:   ${last['close']:.2f}")
            print(f"  Change: ${price_change:+.2f} ({price_change_pct:+.2f}%)")
        else:
            print("\n⚠️  No bars returned (market might be closed)")
        
    except ValueError as e:
        print(f"\n❌ Configuration error: {e}")
        print("\n💡 Make sure to add your API key to .env:")
        print("   echo 'MASSIVE_API_KEY=your_key' >> .env")
    except requests.HTTPError as e:
        print(f"\n❌ API error: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    print("\n" + "=" * 70)
    print("Test complete!")