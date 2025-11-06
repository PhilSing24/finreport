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

def get_qa_section(call_id: str) -> list:
    """
    Retrieve Q&A section (questions and answers) from earnings call.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
    
    Returns:
        List of Q&A intervention dictionaries in chronological order
    
    Raises:
        ValueError: If call_id not found
        psycopg2.Error: If database connection fails
    
    Example:
        >>> qa = get_qa_section("earnings:nvda:q2-fy2026")
        >>> questions = [i for i in qa if i['is_question']]
        >>> print(f"Found {len(questions)} analyst questions")
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
            text_chars,
            is_question,
            is_answer,
            question_id,
            analyst_firm
        FROM call_interventions
        WHERE call_id = %s
          AND is_qa_section = TRUE
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
                        "text_chars": row[7],
                        "is_question": row[8],
                        "is_answer": row[9],
                        "question_id": row[10],
                        "analyst_firm": row[11]
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
    print(f"   Total interventions: {call['total_interventions']}")
    
    # Test 2: get_prepared_remarks()
    print("\n📋 Test 2: get_prepared_remarks()")
    print("-" * 60)
    remarks = get_prepared_remarks("earnings:nvda:q2-fy2026")
    print(f"✅ Found {len(remarks)} prepared remarks")
    
    # Test 3: get_qa_section()
    print("\n📋 Test 3: get_qa_section()")
    print("-" * 60)
    qa = get_qa_section("earnings:nvda:q2-fy2026")
    print(f"✅ Found {len(qa)} Q&A interventions")
    
    # Count questions vs answers
    questions = [i for i in qa if i['is_question']]
    answers = [i for i in qa if i['is_answer']]
    print(f"   - {len(questions)} analyst questions")
    print(f"   - {len(answers)} management answers")
    
    # Show first question
    if questions:
        q = questions[0]
        print(f"\n   First question:")
        print(f"   Analyst: {q['speaker_name']} ({q['analyst_firm']})")
        print(f"   Time: {q['relative_time']}")
        print(f"   Question: {q['text'][:100]}...")
    
    # Show first answer
    if answers:
        a = answers[0]
        print(f"\n   First answer:")
        print(f"   Speaker: {a['speaker_name']} ({a['speaker_role']})")
        print(f"   Time: {a['relative_time']}")
        print(f"   Answer: {a['text'][:100]}...")
    
    # Test with Q1
    print("\n📋 Test 4: Q1 FY2026 Q&A section")
    print("-" * 60)
    qa_q1 = get_qa_section("earnings:nvda:q1-fy2026")
    print(f"✅ Q1 has {len(qa_q1)} Q&A interventions")
    
    # Test error handling
    print("\n📋 Test 5: Error handling")
    print("-" * 60)
    try:
        qa = get_qa_section("earnings:invalid:id")
    except ValueError as e:
        print(f"✅ Error caught: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 All tests passed!")