# src/aifinreport/agents/news_ranker.py
"""
Semantic ranking of news articles using local embeddings
"""
from typing import List, Dict
import numpy as np
from sentence_transformers import SentenceTransformer

# Global model instance (loaded once)
_model = None


def get_embedding(text: str) -> List[float]:
    """
    Get embedding vector for text using local Sentence Transformer model.
    
    Args:
        text: Text to embed
    
    Returns:
        Embedding vector (384 dimensions for all-MiniLM-L6-v2)
    """
    global _model
    
    # Load model on first use (takes ~2 seconds, only once)
    if _model is None:
        print("   Loading embedding model (one-time, ~2 seconds)...")
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        print("   ✅ Model loaded")
    
    # Truncate to model's max length
    text = text[:8000]
    
    # Encode (no API call, runs locally)
    embedding = _model.encode(text, show_progress_bar=False, convert_to_numpy=True)
    
    return embedding.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(a)
    b = np.array(b)
    
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def extract_article_text(article: Dict, max_chars: int = 1500) -> str:
    """
    Extract relevant text from article for embedding.
    
    Args:
        article: Article dict with title, description, full_body
        max_chars: Maximum characters to extract
    
    Returns:
        Combined text for embedding
    """
    parts = []
    
    # Title (most important)
    if article.get('title'):
        parts.append(article['title'])
    
    # Description/summary
    if article.get('description'):
        parts.append(article['description'])
    
    # First part of body
    if article.get('full_body'):
        body = article['full_body']
        # Take first few paragraphs (up to max_chars)
        remaining = max_chars - sum(len(p) for p in parts)
        if remaining > 0:
            parts.append(body[:remaining])
    
    return "\n\n".join(parts)


def rank_articles_by_relevance(
    articles: List[Dict],
    ticker: str,
    quarter: str,
    top_n: int = 10
) -> List[Dict]:
    """
    Rank articles by semantic similarity to earnings expectations query.
    
    Args:
        articles: List of article dicts
        ticker: Company ticker (e.g., "NVDA")
        quarter: Quarter (e.g., "Q3")
        top_n: Number of top articles to return
    
    Returns:
        Top N articles with relevance scores
    """
    if not articles:
        return []
    
    print(f"   Ranking {len(articles)} articles using local embeddings...")
    
    # Create earnings-focused query
    query = f"""Insights about {ticker}'s upcoming {quarter} quarterly earnings results, including:
- Analyst forecasts and consensus estimates
- Revenue and EPS expectations
- Margin outlook and profitability trends
- Guidance changes or updates
- Demand trends and order patterns
- Key risks and headwinds
- Competitive pressures
- Investor sentiment and price targets"""
    
    # Get query embedding (loads model on first call)
    query_embedding = get_embedding(query)
    
    # Embed each article and calculate similarity
    scored_articles = []
    
    for i, article in enumerate(articles):
        # Extract text
        article_text = extract_article_text(article)
        
        # Get embedding
        article_embedding = get_embedding(article_text)
        
        # Calculate similarity
        similarity = cosine_similarity(query_embedding, article_embedding)
        
        # Add to article
        article['relevance_score'] = similarity
        article['_extracted_text'] = article_text  # For debugging
        scored_articles.append(article)
        
        # Progress indicator (every 10 articles)
        if (i + 1) % 10 == 0:
            print(f"   Processed {i + 1}/{len(articles)} articles...")
    
    # Sort by relevance
    ranked = sorted(scored_articles, key=lambda x: x['relevance_score'], reverse=True)
    
    print(f"   ✅ Ranked by semantic relevance")
    
    return ranked[:top_n]


def print_ranked_articles(articles: List[Dict]):
    """Print ranked articles with scores."""
    print(f"\n{'='*70}")
    print(f"Top {len(articles)} Most Relevant Articles (by semantic similarity)")
    print(f"{'='*70}")
    
    for i, article in enumerate(articles, 1):
        score = article.get('relevance_score', 0)
        title = article.get('title', 'No title')
        published = article.get('published_utc', 'No date')
        
        # Format date
        if hasattr(published, 'strftime'):
            date_str = published.strftime('%Y-%m-%d %H:%M')
        else:
            date_str = str(published)
        
        print(f"\n{i}. [Score: {score:.3f}] {title}")
        print(f"   Published: {date_str}")
        
        # Show snippet of description
        if article.get('description'):
            desc = article['description'][:120]
            print(f"   {desc}...")