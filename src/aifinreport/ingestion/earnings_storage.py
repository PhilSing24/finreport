# src/aifinreport/ingestion/earnings_storage.py
"""
Store parsed earnings call data in database.
"""
import psycopg2
from typing import Dict, Any
from aifinreport.config import PG_DSN


def store_earnings_call(
    call_id: str,
    ticker: str,
    fiscal_quarter: str,
    fiscal_year: int,
    call_date: str,
    call_start_utc: str,
    parsed_data: Dict[str, Any]
) -> None:
    """
    Store earnings call and interventions in database.
    
    Args:
        call_id: Unique ID (e.g., "earnings:nvda:q2-fy2026")
        ticker: Stock ticker
        fiscal_quarter: Q1, Q2, Q3, Q4
        fiscal_year: Fiscal year
        call_date: Date of call (YYYY-MM-DD)
        call_start_utc: UTC timestamp of call start
        parsed_data: Output from parse_transcript_file()
    """
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            # 1. Insert earnings_calls record
            cur.execute("""
                INSERT INTO earnings_calls (
                    id, ticker, fiscal_quarter, fiscal_year,
                    call_date, call_start_utc, full_transcript
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    full_transcript = EXCLUDED.full_transcript,
                    created_at = earnings_calls.created_at
            """, (
                call_id,
                ticker,
                fiscal_quarter,
                fiscal_year,
                call_date,
                call_start_utc,
                parsed_data['full_transcript']
            ))
            
            print(f"✅ Stored earnings_calls record: {call_id}")
            
            # 2. Delete old interventions for this call (if re-processing)
            cur.execute("""
                DELETE FROM call_interventions WHERE call_id = %s
            """, (call_id,))
            
            # 3. Insert all interventions
            for intervention in parsed_data['interventions']:
                cur.execute("""
                    INSERT INTO call_interventions (
                        call_id, ticker, timestamp_utc, relative_seconds,
                        relative_time, speaker_name, speaker_role, speaker_type,
                        text, text_chars, sequence_order, is_qa_section,
                        is_question, is_answer, question_id, analyst_firm
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    call_id,
                    ticker,
                    intervention['timestamp_utc'],
                    intervention['relative_seconds'],
                    intervention['relative_time'],
                    intervention['speaker_name'],
                    intervention.get('speaker_role'),
                    intervention['speaker_type'],
                    intervention['text'],
                    intervention['text_chars'],
                    intervention['sequence_order'],
                    intervention.get('is_qa_section', False),
                    intervention.get('is_question', False),
                    intervention.get('is_answer', False),
                    intervention.get('question_id'),
                    intervention.get('analyst_firm')
                ))
            
            print(f"✅ Stored {len(parsed_data['interventions'])} interventions")
        
        conn.commit()


if __name__ == "__main__":
    print("This module is meant to be imported, not run directly.")
    print("Use: from aifinreport.ingestion.earnings_storage import store_earnings_call")