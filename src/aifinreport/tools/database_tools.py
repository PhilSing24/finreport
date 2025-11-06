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

def get_prepared_remarks(call_id: str) -> list:
    """
    Retrieve prepared remarks (non-Q&A interventions) from earnings call.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
    
    Returns:
        List of intervention dictionaries in chronological order
    
    Raises:
        ValueError: If call_id not found
        psycopg2.Error: If database connection fails
    
    Example:
        >>> remarks = get_prepared_remarks("earnings:nvda:q2-fy2026")
        >>> print(f"Found {len(remarks)} prepared remarks")
        >>> print(remarks[0]["speaker_name"])  # First speaker
    """
    # Verify call exists
    _ = get_earnings_call(call_id)  # Raises ValueError if not found
    
    query = """
        SELECT 
            sequence_order,
            speaker_name,
            speaker_role,
            speaker_type,
            timestamp_utc,
            relative_time,
            text,
            text_chars
        FROM call_interventions
        WHERE call_id = %s
          AND (is_qa_section = FALSE OR is_qa_section IS NULL)
        ORDER BY sequence_order
    """
    
    try:
        with psycopg2.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(query, (call_id,))
                results = cur.fetchall()
                
                interventions = []
                for row in results:
                    interventions.append({
                        "sequence_order": row[0],
                        "speaker_name": row[1],
                        "speaker_role": row[2],
                        "speaker_type": row[3],
                        "timestamp_utc": row[4],
                        "relative_time": row[5],
                        "text": row[6],
                        "text_chars": row[7]
                    })
                
                return interventions
    
    except psycopg2.Error as e:
        raise psycopg2.Error(f"Database error: {e}")



if __name__ == "__main__":
    # Test the functions
    print("Testing database tools...")
    print("=" * 60)
    
    # Test 1: get_earnings_call()
    print("\n📋 Test 1: get_earnings_call()")
    print("-" * 60)
    call = get_earnings_call("earnings:nvda:q2-fy2026")
    print(f"✅ {call['ticker']} {call['fiscal_quarter']} {call['fiscal_year']}")
    print(f"   Date: {call['call_date']}")
    print(f"   Time (UTC): {call['call_start_utc']}")
    print(f"   Total interventions: {call['total_interventions']}")
    print(f"   Total speakers: {call['total_speakers']}")
    
    # Test 2: get_prepared_remarks()
    print("\n📋 Test 2: get_prepared_remarks()")
    print("-" * 60)
    remarks = get_prepared_remarks("earnings:nvda:q2-fy2026")
    print(f"✅ Found {len(remarks)} prepared remarks")
    print(f"\n   First 3 speakers:")
    for i, remark in enumerate(remarks[:3], 1):
        print(f"   {i}. {remark['speaker_name']} ({remark['speaker_type']}) at {remark['relative_time']}")
        print(f"      Text preview: {remark['text'][:80]}...")
    
    # Test with Q1
    print("\n📋 Test 3: Q1 FY2026 prepared remarks")
    print("-" * 60)
    remarks_q1 = get_prepared_remarks("earnings:nvda:q1-fy2026")
    print(f"✅ Q1 has {len(remarks_q1)} prepared remarks")
    
    # Test error handling
    print("\n📋 Test 4: Error handling")
    print("-" * 60)
    try:
        remarks = get_prepared_remarks("earnings:invalid:id")
    except ValueError as e:
        print(f"✅ Error caught correctly: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 All tests passed!")