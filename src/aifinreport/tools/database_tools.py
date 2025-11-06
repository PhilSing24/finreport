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

def search_news_around_call(
    call_id: str, 
    time_window: str = "all",
    limit: int = None
) -> list:
    """
    Search for news articles around an earnings call.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
        time_window: 'pre-call' (7 days before), 'during' (±6 hours), 
                     'post-24h' (24 hours after), 'post-7d' (7 days after),
                     or 'all' (14 days: 7 before + 7 after)
        limit: Optional limit on number of articles
    
    Returns:
        List of news article dictionaries
    
    Raises:
        ValueError: If call_id not found or invalid time_window
    
    Example:
        >>> news = search_news_around_call("earnings:nvda:q2-fy2026", "pre-call")
        >>> print(f"Found {len(news)} articles before call")
    """
    from datetime import timedelta
    
    # Get call info
    call = get_earnings_call(call_id)
    call_time = call['call_start_utc']
    ticker = call['ticker']
    
    # Define time ranges
    time_ranges = {
        'pre-call': (call_time - timedelta(days=7), call_time),
        'during': (call_time - timedelta(hours=1), call_time + timedelta(hours=6)),
        'post-24h': (call_time, call_time + timedelta(hours=24)),
        'post-7d': (call_time, call_time + timedelta(days=7)),
        'all': (call_time - timedelta(days=7), call_time + timedelta(days=7))
    }
    
    if time_window not in time_ranges:
        raise ValueError(f"Invalid time_window: {time_window}. Must be one of {list(time_ranges.keys())}")
    
    start_time, end_time = time_ranges[time_window]
    
    query = """
        SELECT 
            id,
            title,
            description,
            url,
            published_utc,
            source,
            tickers
        FROM news_raw
        WHERE %s = ANY(tickers)
          AND published_utc BETWEEN %s AND %s
        ORDER BY published_utc DESC
    """
    
    params = [ticker, start_time, end_time]
    
    if limit:
        query += " LIMIT %s"
        params.append(limit)
    
    try:
        with psycopg2.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                results = cur.fetchall()
                
                articles = []
                for row in results:
                    articles.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "url": row[3],
                        "published_utc": row[4],
                        "source": row[5],
                        "tickers": row[6]
                    })
                
                return articles
    
    except psycopg2.Error as e:
        raise psycopg2.Error(f"Database error: {e}")


def get_analyst_questions(call_id: str) -> list:
    """
    Retrieve only analyst questions from Q&A section.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
    
    Returns:
        List of question dictionaries
    
    Example:
        >>> questions = get_analyst_questions("earnings:nvda:q2-fy2026")
        >>> for q in questions:
        >>>     print(f"{q['analyst_firm']}: {q['text'][:50]}...")
    """
    qa = get_qa_section(call_id)
    return [i for i in qa if i['is_question']]


def get_management_answers(call_id: str, question_id: int = None) -> list:
    """
    Retrieve management answers from Q&A section.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
        question_id: Optional - filter answers to specific question
    
    Returns:
        List of answer dictionaries
    
    Example:
        >>> answers = get_management_answers("earnings:nvda:q2-fy2026")
        >>> ceo_answers = [a for a in answers if 'CEO' in a['speaker_role']]
    """
    qa = get_qa_section(call_id)
    answers = [i for i in qa if i['is_answer']]
    
    if question_id:
        answers = [a for a in answers if a['question_id'] == question_id]
    
    return answers


def get_speaker_interventions(
    call_id: str, 
    speaker_name: str = None,
    speaker_role: str = None,
    speaker_type: str = None
) -> list:
    """
    Get interventions filtered by speaker.
    
    Args:
        call_id: Unique identifier
        speaker_name: Exact name (e.g., "Jensen Huang")
        speaker_role: Role contains (e.g., "CEO", "CFO")
        speaker_type: Type (e.g., "management", "analyst", "operator")
    
    Returns:
        List of intervention dictionaries
    
    Example:
        >>> ceo = get_speaker_interventions("earnings:nvda:q2-fy2026", speaker_role="CEO")
        >>> print(f"CEO made {len(ceo)} statements")
    """
    # Verify call exists
    _ = get_earnings_call(call_id)
    
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
            is_qa_section
        FROM call_interventions
        WHERE call_id = %s
    """
    
    params = [call_id]
    
    if speaker_name:
        query += " AND speaker_name = %s"
        params.append(speaker_name)
    
    if speaker_role:
        query += " AND speaker_role ILIKE %s"
        params.append(f"%{speaker_role}%")
    
    if speaker_type:
        query += " AND speaker_type = %s"
        params.append(speaker_type)
    
    query += " ORDER BY sequence_order"
    
    try:
        with psycopg2.connect(PG_DSN) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
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
                        "is_qa_section": row[8]
                    })
                
                return interventions
    
    except psycopg2.Error as e:
        raise psycopg2.Error(f"Database error: {e}")


def get_question_answer_pairs(call_id: str) -> list:
    """
    Get Q&A as linked question-answer pairs.
    
    Args:
        call_id: Unique identifier (e.g., 'earnings:nvda:q2-fy2026')
    
    Returns:
        List of dictionaries with 'question' and 'answers' keys
    
    Example:
        >>> pairs = get_question_answer_pairs("earnings:nvda:q2-fy2026")
        >>> for pair in pairs:
        >>>     print(f"Q: {pair['question']['analyst_firm']}")
        >>>     print(f"A: {len(pair['answers'])} responses")
    """
    questions = get_analyst_questions(call_id)
    
    pairs = []
    for question in questions:
        q_id = question['sequence_order']
        answers = get_management_answers(call_id, question_id=q_id)
        
        pairs.append({
            'question': question,
            'answers': answers
        })
    
    return pairs


if __name__ == "__main__":
    # Test all database tools
    print("Testing all database tools...")
    print("=" * 70)
    
    call_id = "earnings:nvda:q2-fy2026"
    
    # Test 1: get_earnings_call()
    print("\n1️⃣  get_earnings_call()")
    print("-" * 70)
    call = get_earnings_call(call_id)
    print(f"✅ {call['ticker']} {call['fiscal_quarter']} {call['fiscal_year']}")
    print(f"   Date: {call['call_date']} at {call['call_start_utc']}")
    print(f"   Total: {call['total_interventions']} interventions, {call['total_speakers']} speakers")
    
    # Test 2: get_prepared_remarks()
    print("\n2️⃣  get_prepared_remarks()")
    print("-" * 70)
    remarks = get_prepared_remarks(call_id)
    print(f"✅ {len(remarks)} prepared remarks")
    print(f"   First: {remarks[0]['speaker_name']} at {remarks[0]['relative_time']}")
    
    # Test 3: get_qa_section()
    print("\n3️⃣  get_qa_section()")
    print("-" * 70)
    qa = get_qa_section(call_id)
    print(f"✅ {len(qa)} Q&A interventions")
    
    # Test 4: search_news_around_call()
    print("\n4️⃣  search_news_around_call()")
    print("-" * 70)
    news_pre = search_news_around_call(call_id, "pre-call")
    news_post = search_news_around_call(call_id, "post-24h")
    print(f"✅ Pre-call: {len(news_pre)} articles")
    print(f"✅ Post-24h: {len(news_post)} articles")
    if news_pre:
        print(f"   Sample: {news_pre[0]['title'][:60]}...")
    
    # Test 5: get_analyst_questions()
    print("\n5️⃣  get_analyst_questions()")
    print("-" * 70)
    questions = get_analyst_questions(call_id)
    print(f"✅ {len(questions)} analyst questions")
    if questions:
        q = questions[0]
        print(f"   First: {q['speaker_name']} ({q['analyst_firm']})")
        print(f"   Asked: {q['text'][:60]}...")
    
    # Test 6: get_management_answers()
    print("\n6️⃣  get_management_answers()")
    print("-" * 70)
    answers = get_management_answers(call_id)
    print(f"✅ {len(answers)} management answers")
    ceo_answers = [a for a in answers if a['speaker_role'] and 'CEO' in a['speaker_role']]
    print(f"   CEO answers: {len(ceo_answers)}")
    
    # Test 7: get_speaker_interventions()
    print("\n7️⃣  get_speaker_interventions()")
    print("-" * 70)
    ceo = get_speaker_interventions(call_id, speaker_role="CEO")
    cfo = get_speaker_interventions(call_id, speaker_role="CFO")
    print(f"✅ CEO: {len(ceo)} interventions")
    print(f"✅ CFO: {len(cfo)} interventions")
    
    # Test 8: get_question_answer_pairs()
    print("\n8️⃣  get_question_answer_pairs()")
    print("-" * 70)
    pairs = get_question_answer_pairs(call_id)
    print(f"✅ {len(pairs)} Q&A pairs")
    if pairs:
        pair = pairs[0]
        print(f"   First Q: {pair['question']['analyst_firm']}")
        print(f"   Answers: {len(pair['answers'])} responses")
        for ans in pair['answers']:
            print(f"      - {ans['speaker_name']} ({ans['speaker_role']})")
    
    # Error handling
    print("\n9️⃣  Error handling")
    print("-" * 70)
    try:
        get_earnings_call("earnings:invalid:id")
    except ValueError as e:
        print(f"✅ Invalid call_id caught: {str(e)[:50]}...")
    
    try:
        search_news_around_call(call_id, "invalid-window")
    except ValueError as e:
        print(f"✅ Invalid time_window caught: {str(e)[:50]}...")
    
    print("\n" + "=" * 70)
    print("🎉 All 8 database tools working perfectly!")