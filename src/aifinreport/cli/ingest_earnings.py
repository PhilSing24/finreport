# src/aifinreport/cli/ingest_earnings.py
"""
CLI tool to ingest earnings call transcripts.
"""
import argparse
from pathlib import Path
from datetime import datetime

from aifinreport.ingestion.earnings_parser import parse_transcript_file
from aifinreport.ingestion.earnings_storage import store_earnings_call


def main():
    parser = argparse.ArgumentParser(
        description="Ingest earnings call transcript into database"
    )
    parser.add_argument("file", help="Path to transcript file")
    parser.add_argument("ticker", help="Stock ticker (e.g., NVDA)")
    parser.add_argument("quarter", help="Fiscal quarter (Q1, Q2, Q3, Q4)")
    parser.add_argument("fiscal_year", type=int, help="Fiscal year (e.g., 2026)")
    parser.add_argument("call_date", help="Call date YYYY-MM-DD")
    parser.add_argument("call_time_utc", help="Call start time in UTC (HH:MM format, e.g., 21:00)")
    
    args = parser.parse_args()
    
    # Build call_id
    ticker_lower = args.ticker.lower()
    quarter_lower = args.quarter.lower()
    call_id = f"earnings:{ticker_lower}:{quarter_lower}-fy{args.fiscal_year}"
    
    # Parse call_time_utc
    call_hour, call_min = map(int, args.call_time_utc.split(':'))
    call_datetime = datetime.strptime(args.call_date, '%Y-%m-%d').replace(
        hour=call_hour, minute=call_min, second=0
    )
    
    print(f"\n📋 Ingesting earnings call:")
    print(f"   ID: {call_id}")
    print(f"   File: {args.file}")
    print(f"   Call time (UTC): {call_datetime}")
    
    # Parse transcript
    print(f"\n📄 Parsing transcript...")
    file_path = Path(args.file)
    parsed_data = parse_transcript_file(file_path, call_datetime)
    
    print(f"✅ Parsed {parsed_data['total_interventions']} interventions")
    print(f"   Unique speakers: {parsed_data['total_speakers']}")
    
    # Store in database
    print(f"\n💾 Storing in database...")
    store_earnings_call(
        call_id=call_id,
        ticker=args.ticker.upper(),
        fiscal_quarter=args.quarter.upper(),
        fiscal_year=args.fiscal_year,
        call_date=args.call_date,
        call_start_utc=call_datetime.isoformat(),
        parsed_data=parsed_data
    )
    
    print(f"\n🎉 Success! Earnings call ingested.")
    print(f"\n💡 To verify, run:")
    print(f"   psql postgresql:///finreport -c \"SELECT * FROM earnings_calls WHERE id='{call_id}'\"")


if __name__ == "__main__":
    main()