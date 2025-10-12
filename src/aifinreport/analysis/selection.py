# core/selectors/select_finance_yahoo.py
"""
Select relevant and diverse Yahoo Finance articles for a ticker.
Uses API-aligned field names (url, source, tags).
Scoring prioritizes content relevance (70%) over length (30%).
"""
from typing import List, Dict                                      # Import List and Dict type hints for function annotations (improves code readability and IDE support)
import pandas as pd                                                # Import pandas for DataFrame operations (SQL query results, data manipulation)
from sqlalchemy import text                                        # Import text function for creating parameterized SQL queries (prevents SQL injection)
from sklearn.feature_extraction.text import TfidfVectorizer        # Import TF-IDF vectorizer to convert text into numerical vectors for similarity comparison
from sklearn.metrics.pairwise import cosine_similarity             # Import cosine similarity function to measure how similar two articles are (for MMR diversity)
from aifinreport.database.connection import engine                                    # Import the database engine (SQLAlchemy connection) to execute queries against PostgreSQL

# ==============================================================================
# UNIVERSAL FINANCIAL KEYWORDS (for content scoring)
# ==============================================================================
FINANCIAL_KEYWORDS = [
    # Core earnings & guidance (12)
    "earnings", "eps", "revenue", "profit", "loss", "income",
    "guidance", "outlook", "forecast", "beat", "miss", "results",
    
    # Quarters & periods (8)
    "q1", "q2", "q3", "q4", "quarter", "quarterly", "annual", "fy",
    
    # Analyst actions (5)
    "upgrade", "downgrade", "rating", "price target", "valuation",
    
    # Market movement (10)
    "surge", "plunge", "rally", "drop", "soar", "tumble",
    "jump", "fall", "rise", "climb",
    
    # Corporate actions (8)
    "merger", "acquisition", "buyback", "deal", "investment",
    "partnership", "stake", "divest",
    
    # Operational (8)
    "delivery", "deliveries", "production", "sales", "growth",
    "orders", "backlog", "shipment",
    
    # Financial health (6)
    "margin", "cash flow", "dividend", "debt", "assets", "balance sheet",
    
    # Market position (4)
    "market share", "competition", "leader", "expansion",
    
    # Risk factors (4)
    "lawsuit", "investigation", "recall", "regulatory",
    
    # Indicators (5)
    "%", "billion", "million", "$", "bps",
]

# ==============================================================================
# SCORING FUNCTIONS
# ==============================================================================

def _score_body_length(n: int) -> float:
    """
    Score article body length with plateau curve.
    
    Scoring zones:
    - Too short (<500): 0.0
    - Rising (500-2500): 0.0 → 1.0 (linear increase)
    - Peak (2500): 1.0 (optimal length)
    - Tapering (2500-6000): 1.0 → 0.8 (gentle decline)
    - Too long (>6000): 0.8 (capped)
    
    Args:
        n: Number of characters in article body
    
    Returns:
        Score between 0.0 and 1.0
    """
    # If None or too short, return 0 (insufficient content)
    if n is None or n <= 500:
        return 0.0
    
    # If very long, cap at 0.8 (may contain fluff or be off-topic)
    if n >= 6000:
        return 0.8
    
    # Rising phase: 500 to 2500 characters (building substance)
    # Linear increase from 0.0 to 1.0
    if n <= 2500:
        return (n - 500) / 2000.0
    
    # Tapering phase: 2500 to 6000 characters (getting long)
    # Gentle decline from 1.0 to 0.8
    return 0.8 + (6000 - n) / 3500.0 * 0.2


def _score_content_relevance(title: str, description: str, summary: str) -> float:
    """
    Score content relevance using multiple text signals.
    
    This function checks financial keywords across three sources:
    - Title: highest weight (most curated by editors)
    - Description: medium weight (original from Tiingo API)
    - Summary: medium weight (extracted by TF-IDF)
    
    Weights within content score:
    - Title: 40% - most important, curated signal
    - Description: 30% - original content from source
    - Summary: 30% - our extraction of key points
    
    Args:
        title: Article title from Tiingo API
        description: Article description from Tiingo API
        summary: Generated summary from TF-IDF extraction
    
    Returns:
        Score between 0.0 and 1.0
    """
    score = 0.0
    
    # 1. Title keywords (40% of content relevance score)
    # Title is most curated - editors choose impactful words
    if title:
        # Convert to lowercase for case-insensitive matching
        title_lower = title.lower()
        # Count keyword matches in title
        title_matches = sum(1 for kw in FINANCIAL_KEYWORDS if kw in title_lower)
        # Normalize: 6 keywords = max score of 0.4
        # Each keyword contributes 0.4/6 = ~0.067
        title_score = min(title_matches / 6.0, 1.0) * 0.4
        score += title_score
    
    # 2. Description keywords (30% of content relevance score)
    # Description from Tiingo API - original article summary
    if description:
        # Convert to lowercase for case-insensitive matching
        desc_lower = description.lower()
        # Count unique keyword matches (using set to avoid double-counting)
        desc_matches = len({kw for kw in FINANCIAL_KEYWORDS if kw in desc_lower})
        # Normalize: 10 unique keywords = max score of 0.3
        # Each keyword contributes 0.3/10 = 0.03
        desc_score = min(desc_matches / 10.0, 1.0) * 0.3
        score += desc_score
    
    # 3. Summary keywords (30% of content relevance score)
    # Summary generated by our TF-IDF - extracted key paragraphs
    if summary:
        # Convert to lowercase for case-insensitive matching
        summ_lower = summary.lower()
        # Count unique keyword matches (using set to avoid double-counting)
        summ_matches = len({kw for kw in FINANCIAL_KEYWORDS if kw in summ_lower})
        # Normalize: 10 unique keywords = max score of 0.3
        # Each keyword contributes 0.3/10 = 0.03
        summ_score = min(summ_matches / 10.0, 1.0) * 0.3
        score += summ_score
    
    # Cap at 1.0 (should not exceed this, but safety check)
    return min(score, 1.0)


def calculate_article_score(article: Dict) -> float:
    """
    Calculate composite relevance score for an article.
    
    New approach: prioritizes content relevance over raw length.
    
    Weights:
    - 30% Body length (objective quality indicator via plateau curve)
    - 70% Content relevance (financial keywords across title/description/summary)
    
    The 70% content weight is distributed as:
    - 28% from title keywords (0.70 × 0.40)
    - 21% from description keywords (0.70 × 0.30)
    - 21% from summary keywords (0.70 × 0.30)
    
    This approach:
    - Avoids circular logic (no scoring based solely on our generated summary length)
    - Prioritizes "what it's about" over "how long it is"
    - Uses multiple independent signals for robustness
    - Filters out long but off-topic articles
    
    Args:
        article: Dictionary with article fields (title, description, summary, full_body_chars)
    
    Returns:
        Score between 0.0 and 1.0
    """
    # Body length score (30% weight) - objective quality indicator
    # Uses plateau curve to favor articles around 2500 characters
    body_score = _score_body_length(article.get("full_body_chars") or 0)
    
    # Content relevance score (70% weight) - multi-signal relevance
    # Checks financial keywords in title, description, and summary
    content_score = _score_content_relevance(
        article.get("title") or "",        # From Tiingo API
        article.get("description") or "",  # From Tiingo API
        article.get("summary") or ""       # Generated by us
    )
    
    # Weighted combination: 30% length, 70% content
    # This prioritizes financial relevance over raw article length
    total = 0.30 * body_score + 0.70 * content_score
    
    # Round to 6 decimal places for consistency
    return round(total, 6)


# ==============================================================================
# DIVERSITY FUNCTIONS (MMR)
# ==============================================================================

def apply_mmr_diversity(articles: List[Dict], max_articles: int, lambda_param: float = 0.5) -> List[Dict]:
    """
    Apply Maximum Marginal Relevance to select diverse articles.
    
    MMR balances two competing objectives:
    1. Select high-scoring articles (relevance)
    2. Select articles different from already-selected ones (diversity)
    
    Process:
    1. Convert articles to TF-IDF vectors (title + summary)
    2. Calculate cosine similarity matrix (how similar articles are)
    3. Start with highest-scored article
    4. Iteratively select articles that maximize: λ×relevance - (1-λ)×similarity
    
    Uses title + summary for semantic similarity via TF-IDF.
    
    Args:
        articles: Articles with '__score' field
        max_articles: Max articles to select
        lambda_param: Balance factor (0.5 = equal relevance/diversity weight)
                     Higher λ = more focus on relevance
                     Lower λ = more focus on diversity
    
    Returns:
        Diverse subset of articles
    """
    # If we have fewer articles than requested, return all
    if len(articles) <= max_articles:
        return articles
    
    # Build text representations (title + summary for best accuracy)
    # Combining both gives richer semantic context than either alone
    texts = [
        f"{a.get('title', '')} {a.get('summary', '')}"
        for a in articles
    ]
    
    # Calculate TF-IDF similarity matrix
    # TF-IDF converts text to vectors, weighing rare words higher
    vectorizer = TfidfVectorizer(max_features=100, stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(texts)
    
    # Cosine similarity: measures how similar two articles are (0=different, 1=identical)
    similarities = cosine_similarity(tfidf_matrix)
    
    # MMR selection algorithm
    selected_idx = []           # Indices of selected articles
    remaining_idx = set(range(len(articles)))  # Indices still available
    
    # Step 1: Pick highest-scored article (best relevance)
    best_idx = max(remaining_idx, key=lambda i: articles[i]['__score'])
    selected_idx.append(best_idx)
    remaining_idx.remove(best_idx)
    
    # Step 2: Iteratively pick articles balancing score and diversity
    while len(selected_idx) < max_articles and remaining_idx:
        best_mmr = -float('inf')  # Track best MMR score
        best_candidate = None      # Track best candidate
        
        # Evaluate each remaining article
        for candidate in remaining_idx:
            # Relevance component: how good is this article?
            relevance = articles[candidate]['__score']
            
            # Diversity component: how similar is this to already-selected articles?
            # We take the MAX similarity (worst case) to avoid redundancy
            max_similarity = max(
                similarities[candidate][selected]
                for selected in selected_idx
            )
            
            # MMR score: balance relevance and diversity
            # λ * relevance - (1-λ) * similarity
            # High relevance and low similarity = high MMR score
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_similarity
            
            # Track the best candidate
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_candidate = candidate
        
        # Add best candidate to selected set
        if best_candidate is not None:
            selected_idx.append(best_candidate)
            remaining_idx.remove(best_candidate)
    
    # Return selected articles in order of selection
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
    2. Deduplicate by title + source (keep most recent)
    3. Score articles by financial relevance (30% length, 70% content)
    4. Apply MMR for diversity
    
    Args:
        ticker: Stock symbol (e.g., 'NVDA', 'AAPL')
        start_date: Start date 'YYYY-MM-DD' (inclusive)
        end_date: End date 'YYYY-MM-DD' (exclusive)
        max_articles: Maximum articles to return
        min_body_chars: Minimum article body length (filters snippets)
        use_mmr: Use MMR diversity (True) or just top-scored (False)
    
    Returns:
        List of article dictionaries, sorted by relevance (or MMR-diverse if use_mmr=True)
    """
    # Query database (using API-aligned field names)
    # Uses parameterized query to prevent SQL injection
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
    
    # Query parameters (safely passed to prevent SQL injection)
    params = {
        "ticker": ticker.upper(),
        "start": start_date,
        "end": end_date,
        "min_chars": min_body_chars,
    }
    
    # Execute query and load into pandas DataFrame
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params=params)
    
    # If no articles found, return empty list
    if df.empty:
        return []
    
    # Normalize tags to list (keep for potential future use, though not used in scoring)
    def normalize_tags(val):
        """Convert tags from various formats to consistent list."""
        if val is None:
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [k.strip() for k in val.split(",") if k.strip()]
        return list(val) if hasattr(val, "__iter__") else []
    
    df["tags"] = df["tags"].map(normalize_tags)
    
    # Deduplicate by (title, source), keep latest
    # This handles cases where same article appears multiple times (updates, corrections)
    dedup_key = df["title"].fillna("").str.lower() + "||" + df["source"].fillna("")
    df = (
        df.assign(_key=dedup_key)
          .sort_values("published_utc")           # Sort by time (earliest first)
          .drop_duplicates("_key", keep="last")   # Keep most recent version
          .drop(columns=["_key"])                  # Remove temporary key column
    )
    
    # Score all articles using 30/70 length/content approach
    articles = df.to_dict(orient="records")
    for article in articles:
        article["__score"] = calculate_article_score(article)
    
    # Sort by score (highest first)
    articles.sort(key=lambda x: x["__score"], reverse=True)
    
    # Apply diversity or just take top-N
    if use_mmr and max_articles:
        # Use MMR to select diverse articles (avoids redundant coverage)
        final_articles = apply_mmr_diversity(articles, max_articles)
    else:
        # Just take top-scored articles (may have redundant content)
        final_articles = articles[:max_articles] if max_articles else articles
    
    # Remove internal score field before returning (clean output)
    return [
        {k: v for k, v in article.items() if k != "__score"}
        for article in final_articles
    ]
