# core/data/summarize_text.py
"""
Generate simple extractive summaries using TF-IDF.
No keyword boosting needed - content validation already ensures relevance.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np


def split_into_paragraphs(text: str):
    """Split text into substantial paragraphs (>100 chars)."""
    return [p.strip() for p in text.split("\n") if len(p.strip()) > 100]


def summarize_article(text: str, ticker: str = None):
    """
    Generate extractive summary from article text.
    
    Uses TF-IDF to select the most important 2 paragraphs.
    No keyword boosting needed since content validation ensures relevance.
    
    Args:
        text: Full article body text
        ticker: Ticker symbol (unused, kept for API compatibility)
    
    Returns:
        Summary text (top 2 paragraphs) or None if no content
    """
    paras = split_into_paragraphs(text)
    if not paras:
        return None
    
    if len(paras) == 1:
        return paras[0]
    
    # Score paragraphs using TF-IDF
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(paras)
    scores = np.asarray(X.sum(axis=1)).ravel()
    
    # Rank by score and take top 2
    ranked = [p for _, p in sorted(zip(scores, paras), reverse=True)]
    summary = "\n\n".join(ranked[:2])
    
    return summary.strip()