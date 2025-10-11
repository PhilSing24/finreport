# core/selectors/select_finance_yahoo.py
"""
Select relevant and diverse Yahoo Finance articles for a ticker.
Uses API-aligned field names (url, source, tags).
Scoring without relying on Tiingo's tags - uses summary length, body length, and title signals.
"""
from typing import List, Dict
import pandas as pd
from sqlalchemy import text
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from core.data.db import engine

# ==============================================================================
# UNIVERSAL FINANCIAL KEYWORDS (for title scoring)
# ==============================================================================
FINANCIAL_TITLE_KEYWORDS = [
    "guidance", "margin", "eps", "revenue", "earnings", "profit",
    "beat", "miss", "outlook", "forecast", "upgrade", "downgrade",
    "q1", "q2", "q3", "q4", "%", "surge", "plunge", "rally", "drop",
    "delivery", "deliveries", "production", "sales", "growth",
]


# ==============================================================================
# SCORING FUNCTIONS
# ==============================================================================

def _score_body_length(n: int) -> float:
    """
    Score article body length with plateau curve.
    - Too short (<500): 0.0
    - Optimal (2500): 1.0  
    - Too long (>6000): 0.8
    """
    if n is None or n <= 500:
        return 0.0
    if n >= 6000:
        return 0.8
    
    # Rise to peak at 2500
    if n <= 2500:
        return (n - 500) / 2000.0
    
    # Taper after peak
    return 0.8 + (6000 - n) / 3500.0 * 0.2


def _score_title_signals(title: str) -> float:
    """Give bonus for financial keywords in title."""
    if not title:
        return 0.0
    
    title_lower = title.lower()
    score = sum(0.025 for kw in FINANCIAL_TITLE_KEYWORDS if kw in title_lower)
    return min(score, 0.15)  # Cap at 0.15


def calculate_article_score(article: Dict) -> float:
    """
    Calculate composite relevance score for an article.
    
    Weights (no longer using unreliable Tiingo tags):
    - 60% Summary length (substantial content indicator)
    - 30% Body length (quality indicator)
    - 10% Title signals (topic relevance)
    """
    # Summary length score (max 1200 chars)
    summary_len = len(article.get("summary") or "")
    summary_score = min(summary_len, 1200) / 1200.0
    
    # Body length score
    body_score = _score_body_length(article.get("full_body_chars") or 0)
    
    # Title signal score
    title_score = _score_title_signals(article.get("title") or "")
    
    # Weighted combination
    total = (
        0.60 * summary_score +
        0.30 * body_score +
        0.10 * title_score
    )
    
    return round(total, 6)


# ==============================================================================
# DIVERSITY FUNCTIONS (MMR)
# ==============================================================================

def apply_mmr_diversity(articles: List[Dict], max_articles: int, lambda_param: float = 0.5) -> List[Dict]:
    """
    Apply Maximum Marginal Relevance to select diverse articles.
    
    Uses title + summary for semantic similarity via TF-IDF.
    Balances relevance (score) with diversity (uniqueness).
    
    Args:
        articles: Articles with '__score' field
        max_articles: Max articles to select
        lambda_param: Balance factor (0.5 = equal relevance/diversity weight)
    
    Returns:
        Diverse subset of articles
    """
    if len(articles) <= max_articles:
        return articles
    
    # Build text representations (title + summary for best accuracy)
    texts = [
        f"{a.get('title', '')} {a.get('summary', '')}"
        for a in articles
    ]
    
    # Calculate TF-IDF similarity matrix
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(texts)
    similarities = cosine_similarity(tfidf_matrix)
    
    # MMR selection
    selected_idx = []
    remaining_idx = set(range(len(articles)))
    
    # Step 1: Pick highest-scored article
    best_idx = max(remaining_idx, key=lambda i: articles[i]['__score'])
    selected_idx.append(best_idx)
    remaining_idx.remove(best_idx)
    
    # Step 2: Iteratively pick articles balancing score and diversity
    while len(selected_idx) < max_articles and remaining_idx:
        best_mmr = -float('inf')
        best_candidate = None
        
        for candidate in remaining_idx:
            # Relevance component
            relevance = articles[candidate]['__score']
            
            # Diversity component (distance from already-selected)
            max_similarity = max(
                similarities[candidate][selected]
                for selected in selected_idx
            )
            
            # MMR score: balance relevance and diversity
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
            
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_candidate = candidate
        
        if best_candidate is not None:
            selected_idx.append(best_candidate)
            remaining_idx.remove(best_candidate)
    
    return [articles[i] for i in selected_idx]


# ==============================================================================
# MAIN SELECTION FUNCTION
# ==============================================================================

def select_articles(
    ticker: str,
    start_date: str,
    end_date: str,
    max_articles: int = 12,
    min_body_chars: int = 800,
    use_mmr: bool = True,
) -> List[Dict]:
    """
    Select relevant and diverse Yahoo Finance articles for a ticker.
    
    Process:
    1. Query database for articles matching filters
    2. Deduplicate by title + source
    3. Score articles by financial relevance
    4. Apply MMR for diversity (optional)
    
    Args:
        ticker: Stock symbol (e.g., 'NVDA', 'AAPL')
        start_date: Start date 'YYYY-MM-DD' (inclusive)
        end_date: End date 'YYYY-MM-DD' (exclusive)
        max_articles: Maximum articles to return
        min_body_chars: Minimum article body length
        use_mmr: Use MMR diversity (True) or just top-scored (False)
    
    Returns:
        List of article dictionaries
    """
    # Query database (using API-aligned field names)
    query = text("""
        SELECT
            id, published_utc, published_date_utc,
            title, url, source,
            tickers, description, summary, tags, 
            full_body, full_body_chars
        FROM news_raw
        WHERE source = 'finance.yahoo.com'
          AND :ticker = ANY(tickers)
          AND published_date_utc >= CAST(:start AS date)
          AND published_date_utc < CAST(:end AS date)
          AND fetch_status = 'ok'
          AND full_body IS NOT NULL
          AND full_body_chars >= :min_chars
        ORDER BY published_utc
    """)
    
    params = {
        "ticker": ticker.upper(),
        "start": start_date,
        "end": end_date,
        "min_chars": min_body_chars,
    }
    
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    
    if df.empty:
        return []
    
    # Normalize tags to list (keep for potential future use)
    def normalize_tags(val):
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [k.strip() for k in val.split(",") if k.strip()]
        return list(val) if hasattr(val, "__iter__") else []
    
    df["tags"] = df["tags"].map(normalize_tags)
    
    # Deduplicate by (title, source), keep latest
    dedup_key = df["title"].fillna("").str.lower() + "||" + df["source"].fillna("")
    df = (
        df.assign(_key=dedup_key)
          .sort_values("published_utc")
          .drop_duplicates("_key", keep="last")
          .drop(columns=["_key"])
    )
    
    # Score all articles
    articles = df.to_dict(orient="records")
    for article in articles:
        article["__score"] = calculate_article_score(article)
    
    # Sort by score
    articles.sort(key=lambda x: x["__score"], reverse=True)
    
    # Apply diversity or just take top-N
    if use_mmr and max_articles:
        final_articles = apply_mmr_diversity(articles, max_articles)
    else:
        final_articles = articles[:max_articles] if max_articles else articles
    
    # Remove internal score field
    return [
        {k: v for k, v in article.items() if k != "__score"}
        for article in final_articles
    ]