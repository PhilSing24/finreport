# src/aifinreport/ingestion/fetchers.py
from __future__ import annotations
import httpx
import trafilatura
from readability import Document

# A normal browser UA helps reduce 403s
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0 Safari/537.36")

def fetch_article_text(url: str, timeout: int = 20) -> tuple[str | None, str | None]:
    """
    Fetches a Yahoo Finance article and extracts clean text.
    Returns: (text or None, extractor_used or None)
    """
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return None, f"http_{r.status_code}"
        html = r.text

        # 1) Try Trafilatura first (best general extractor)
        text = trafilatura.extract(html, url=url, favor_recall=True, include_links=False)
        if text and len(text.strip()) >= 200:
            return text.strip(), "trafilatura"

        # 2) Fallback: readability → then clean that with trafilatura again
        try:
            doc = Document(html)
            # Pull the “content summary” (main article HTML) and clean again
            text2 = trafilatura.extract(doc.summary(html_partial=True)) or ""
            text2 = text2.strip()
            if len(text2) >= 200:
                return text2, "readability+trafilatura"
        except Exception:
            pass

        # If both paths fail, return short/None
        return None, "parse_fail"

    except httpx.ReadTimeout:
        return None, "timeout"
    except Exception as e:
        return None, f"error:{type(e).__name__}"

