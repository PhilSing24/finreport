import psycopg2, sys
from datetime import date, timedelta
from core.data.summarize_text import summarize_article
from core.data.keywords import extract_keywords

def enrich_summary_keywords(day: date):
    conn = psycopg2.connect("dbname=finreport")
    cur = conn.cursor()

    cur.execute("""
        SELECT id, tickers[1], full_body
        FROM news_raw
        WHERE published_date_utc = %s
          AND fetch_status='ok'
          AND (summary IS NULL OR keywords IS NULL);
    """, (day,))
    rows = cur.fetchall()

    ok = 0
    for id_, ticker, body in rows:
        summary = summarize_article(body, ticker)
        kw = extract_keywords(body, ticker)
        cur.execute("""
            UPDATE news_raw
            SET summary=%s, keywords=%s
            WHERE id=%s;
        """, (summary, kw, id_))
        ok += 1

    conn.commit()
    print(f"[enrich_summary_keywords] {ok} rows updated for {day}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    day = sys.argv[1] if len(sys.argv)>1 else str(date.today()-timedelta(days=1))
    enrich_summary_keywords(day)
