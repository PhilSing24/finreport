# src/aifinreport/cli/ingest_press_release.py
"""
Ingest earnings press releases into news_raw table.
"""
import sys
import argparse
from datetime import datetime
from pathlib import Path
import psycopg2
from PyPDF2 import PdfReader
from aifinreport.config import PG_DSN


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text
    """
    reader = PdfReader(pdf_path)
    text = ""
    
    for page in reader.pages:
        text += page.extract_text()
    
    return text


def generate_press_release_id(ticker: str, quarter: str, year: int) -> str:
    """Generate unique ID for press release."""
    quarter_lower = quarter.lower()
    return f"pr:{ticker.lower()}:{quarter_lower}-fy{year}"


def generate_call_id(ticker: str, quarter: str, year: int) -> str:
    """Generate earnings call ID to link to."""
    quarter_lower = quarter.lower()
    return f"earnings:{ticker.lower()}:{quarter_lower}-fy{year}"


def store_press_release(
    pr_id: str,
    ticker: str,
    title: str,
    full_text: str,
    published_utc: datetime,
    related_call_id: str,
    source_file: str
) -> None:
    """
    Store press release in news_raw table.
    
    Args:
        pr_id: Unique press release ID
        ticker: Stock ticker
        title: Press release title
        full_text: Full text content
        published_utc: Publication timestamp
        related_call_id: ID of related earnings call
        source_file: Original file path
    """
    with psycopg2.connect(PG_DSN) as conn:
        with conn.cursor() as cur:
            # Insert into news_raw
            cur.execute("""
                INSERT INTO news_raw (
                    id,
                    title,
                    published_utc,
                    tickers,
                    full_body,
                    source,
                    is_press_release,
                    press_release_type,
                    related_call_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    full_body = EXCLUDED.full_body,
                    title = EXCLUDED.title,
                    related_call_id = EXCLUDED.related_call_id
            """, (
                pr_id,
                title,
                published_utc,
                [ticker],  # Array of tickers
                full_text,
                f"Official Press Release (from {Path(source_file).name})",
                True,  # is_press_release
                'earnings',  # press_release_type
                related_call_id
            ))
            
        conn.commit()


def main():
    """Main ingestion function."""
    parser = argparse.ArgumentParser(
        description='Ingest earnings press release PDF into database'
    )
    parser.add_argument(
        'pdf_file',
        help='Path to press release PDF file'
    )
    parser.add_argument(
        'ticker',
        help='Stock ticker (e.g., NVDA)'
    )
    parser.add_argument(
        'quarter',
        help='Fiscal quarter (e.g., Q3)'
    )
    parser.add_argument(
        'year',
        type=int,
        help='Fiscal year (e.g., 2026)'
    )
    parser.add_argument(
        'published_time',
        help='Publication time in UTC (YYYY-MM-DD HH:MM format)'
    )
    
    args = parser.parse_args()
    
    # Validate file exists
    pdf_path = Path(args.pdf_file)
    if not pdf_path.exists():
        print(f"❌ Error: File not found: {pdf_path}")
        sys.exit(1)
    
    print("📋 Ingesting press release:")
    print(f"   File: {pdf_path}")
    print(f"   Ticker: {args.ticker}")
    print(f"   Quarter: {args.quarter} FY{args.year}")
    print(f"   Published: {args.published_time} UTC")
    
    # Parse publication time
    try:
        published_utc = datetime.strptime(args.published_time, '%Y-%m-%d %H:%M')
    except ValueError:
        print("❌ Error: Invalid time format. Use YYYY-MM-DD HH:MM")
        sys.exit(1)
    
    # Extract text from PDF
    print("\n📄 Extracting text from PDF...")
    try:
        full_text = extract_text_from_pdf(str(pdf_path))
        
        # Extract title from first line or generate
        lines = full_text.split('\n')
        title = None
        for line in lines:
            line = line.strip()
            if line and len(line) > 10:  # Skip very short lines
                title = line
                break
        
        if not title:
            title = f"{args.ticker} Announces Financial Results for {args.quarter} Fiscal {args.year}"
        
        print(f"✅ Extracted {len(full_text)} characters")
        print(f"   Title: {title[:80]}...")
        
    except Exception as e:
        print(f"❌ Error extracting text: {e}")
        sys.exit(1)
    
    # Generate IDs
    pr_id = generate_press_release_id(args.ticker, args.quarter, args.year)
    call_id = generate_call_id(args.ticker, args.quarter, args.year)
    
    print(f"\n💾 Storing in database...")
    print(f"   Press Release ID: {pr_id}")
    print(f"   Related Call ID: {call_id}")
    
    try:
        store_press_release(
            pr_id=pr_id,
            ticker=args.ticker,
            title=title,
            full_text=full_text,
            published_utc=published_utc,
            related_call_id=call_id,
            source_file=str(pdf_path)
        )
        
        print(f"✅ Stored press release in news_raw")
        
    except Exception as e:
        print(f"❌ Error storing press release: {e}")
        sys.exit(1)
    
    print("\n🎉 Success! Press release ingested.")
    print("\n💡 To verify, run:")
    print(f"   psql postgresql:///finreport -c \"SELECT id, title, is_press_release, related_call_id FROM news_raw WHERE id='{pr_id}'\"")


if __name__ == "__main__":
    main()