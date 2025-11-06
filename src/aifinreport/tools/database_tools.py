"""
Database tools for querying earnings call data.
"""
import psycopg2
from datetime import datetime
from typing import Dict, Optional
from aifinreport.config import PG_DSN


def get_earnings_call(call_id: str) -> Dict:
    """
    Retrieve earnings call metadata by ID.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
    
    Returns:
        Dictionary with call metadata
    
    Raises:
        ValueError: If call_id not found
        psycopg2.Error: If database connection fails
    
    Example:
        >>> call = get_earnings_call("earnings:nvda:q2-fy2026")
        >>> print(call["ticker"])
        'NVDA'
    """
    query = """
        SELECT 
            id,
            ticker,
            fiscal_quarter,
            fiscal_year,
            call_date,
            call_start_utc
        FROM earnings_calls
        WHERE id = %s
    """
    
    try:
        with psycopg2.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (call_id,))
                result = cur.fetchone()
                
                if result is None:
                    raise ValueError(f"Earnings call not found: {call_id}")
                
                # Unpack result
                (id, ticker, fiscal_quarter, fiscal_year, 
                 call_date, call_start_utc) = result
                
                # Get intervention count
                cur.execute("""
                    SELECT COUNT(*) 
                    FROM call_interventions 
                    WHERE call_id = %s
                """, (call_id,))
                total_interventions = cur.fetchone()[0]
                
                # Get speaker count
                cur.execute("""
                    SELECT COUNT(DISTINCT speaker_name) 
                    FROM call_interventions 
                    WHERE call_id = %s
                """, (call_id,))
                total_speakers = cur.fetchone()[0]
                
                return {
                    "id": id,
                    "ticker": ticker,
                    "fiscal_quarter": fiscal_quarter,
                    "fiscal_year": fiscal_year,
                    "call_date": call_date,
                    "call_start_utc": call_start_utc,
                    "total_interventions": total_interventions,
                    "total_speakers": total_speakers
                }
    
    except psycopg2.Error as e:
        raise psycopg2.Error(f"Database error: {e}")


if __name__ == "__main__":
    # Test the function
    print("Testing get_earnings_call()...")
    
    # Test Q2
    call = get_earnings_call("earnings:nvda:q2-fy2026")
    print(f"\n✅ Q2 FY2026:")
    print(f"   Ticker: {call['ticker']}")
    print(f"   Quarter: {call['fiscal_quarter']} {call['fiscal_year']}")
    print(f"   Date: {call['call_date']}")
    print(f"   Time (UTC): {call['call_start_utc']}")
    print(f"   Interventions: {call['total_interventions']}")
    print(f"   Speakers: {call['total_speakers']}")
    
    # Test Q1
    call = get_earnings_call("earnings:nvda:q1-fy2026")
    print(f"\n✅ Q1 FY2026:")
    print(f"   Ticker: {call['ticker']}")
    print(f"   Quarter: {call['fiscal_quarter']} {call['fiscal_year']}")
    print(f"   Interventions: {call['total_interventions']}")
    
    # Test invalid ID
    try:
        call = get_earnings_call("earnings:invalid:id")
    except ValueError as e:
        print(f"\n✅ Error handling works: {e}")
    
    print("\n🎉 All tests passed!")