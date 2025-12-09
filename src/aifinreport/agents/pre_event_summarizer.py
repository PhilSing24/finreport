# src/aifinreport/agents/pre_event_summarizer.py
"""
Pre-Event Expectations Summarizer
Analyzes news articles to extract market expectations before earnings press release.
"""
from typing import Dict, List
import json
import os
from mistralai import Mistral


# Universal prompt template
EXPECTATIONS_PROMPT = """You are analyzing financial news articles published BEFORE a company's earnings press release.

Your task: Summarize what the market EXPECTS to see in the upcoming press release.

---

CONTEXT:
Company: {company_name}
Quarter: {quarter}
Number of articles analyzed: {article_count}
Published: In the week before the earnings press release

---

INPUT:
{articles_text}

---

YOUR TASK:

Analyze these articles and extract what analysts and investors EXPECT to be announced in the press release.

Focus on:
1. EXPECTED FINANCIAL RESULTS
   - What specific metrics are discussed? (revenue, EPS, margins, segment performance, etc.)
   - For each metric: What is the expected value or trend?
   - How confident is the consensus? (based on how many articles mention it)

2. EXPECTED FORWARD GUIDANCE
   - What future outlook do analysts expect management to provide in the press release?
   - What time periods are mentioned? (next quarter, full year, longer-term)
   - What specific guidance items are being watched?

3. KEY THEMES & NARRATIVES
   - What business trends/topics are repeatedly discussed?
   - What are the main drivers of optimism or concern?
   - Are there divergent views among analysts?

4. POTENTIAL SURPRISES
   - What would constitute a positive surprise (beat expectations)?
   - What would constitute a negative surprise (miss expectations)?
   - What unexpected information could significantly move the stock?

5. MARKET SENTIMENT
   - What is the overall tone? (optimistic, cautious, pessimistic, mixed)
   - What is the consensus view on the likely outcome?
   - Are there notable contrarian opinions?

---

CRITICAL RULES:
- Extract ONLY information explicitly stated in the articles
- Use exact numbers when provided (e.g., "$32.5B" not "around $32B")
- Indicate confidence based on article consensus:
  * HIGH if 70%+ of articles mention it
  * MEDIUM if 40-70% mention it
  * LOW if <40% mention it
- If articles show disagreement, note both viewpoints
- Group similar topics together
- Prioritize by importance and frequency of mention

---

OUTPUT FORMAT:

Return valid JSON with this exact structure:

{{
  "expected_results": {{
    "metric_name": {{
      "expected_value": "specific number, range, or directional trend",
      "confidence": "HIGH|MEDIUM|LOW",
      "article_mentions": number,
      "percentage_of_articles": percentage,
      "context": "brief explanation of why this expectation exists"
    }}
  }},
  
  "expected_guidance": [
    {{
      "time_period": "which period (e.g., 'Q4 FY2026', 'Full Year FY2026', 'Long-term')",
      "guidance_item": "what specific guidance",
      "expected_content": "what analysts expect to hear",
      "importance": "why this matters to investors",
      "article_mentions": number,
      "confidence": "HIGH|MEDIUM|LOW"
    }}
  ],
  
  "key_themes": [
    {{
      "theme_name": "descriptive name",
      "summary": "what is being discussed",
      "sentiment": "positive|negative|neutral|mixed",
      "article_mentions": number,
      "supporting_points": ["key point 1", "key point 2"]
    }}
  ],
  
  "surprise_scenarios": {{
    "positive": [
      {{
        "scenario": "what would be a positive surprise",
        "impact": "expected market reaction if this happens",
        "likelihood": "based on article discussion"
      }}
    ],
    "negative": [
      {{
        "scenario": "what would be a negative surprise",
        "impact": "expected market reaction if this happens",
        "likelihood": "based on article discussion"
      }}
    ]
  }},
  
  "market_sentiment": {{
    "overall_tone": "description",
    "consensus_expectation": "what most analysts think will happen",
    "bull_case": "optimistic view if mentioned",
    "bear_case": "pessimistic view if mentioned",
    "divergent_views": "notable disagreements among analysts, if any"
  }}
}}

---

IMPORTANT:
- This analysis is for what will be ANNOUNCED in the press release
- Do NOT include questions for Q&A (that happens later in the earnings call)
- Focus on EXPECTATIONS about numbers, guidance, and announcements
- Be precise and evidence-based
"""


def format_articles_for_prompt(ranked_articles: List[Dict], max_chars_per_article: int = 1500) -> str:
    """
    Format articles into text for the LLM prompt.
    
    Args:
        ranked_articles: List of ranked article dicts
        max_chars_per_article: Max chars to include per article
    
    Returns:
        Formatted text string
    """
    article_texts = []
    
    for i, article in enumerate(ranked_articles, 1):
        # Build article text
        parts = []
        
        # Title
        if article.get('title'):
            parts.append(f"TITLE: {article['title']}")
        
        # Relevance score
        if article.get('relevance_score'):
            parts.append(f"Relevance Score: {article['relevance_score']:.3f}")
        
        # Published date
        if article.get('published_utc'):
            pub_date = article['published_utc']
            date_str = pub_date.strftime('%Y-%m-%d') if hasattr(pub_date, 'strftime') else str(pub_date)
            parts.append(f"Published: {date_str}")
        
        # Description
        if article.get('description'):
            parts.append(f"\nSUMMARY: {article['description']}")
        
        # Body excerpt
        if article.get('full_body'):
            body = article['full_body'][:max_chars_per_article]
            parts.append(f"\nCONTENT EXCERPT:\n{body}")
        elif article.get('_extracted_text'):
            # From semantic ranking
            text = article['_extracted_text'][:max_chars_per_article]
            parts.append(f"\nCONTENT:\n{text}")
        
        # Combine
        article_text = f"=== ARTICLE {i} ===\n" + "\n".join(parts)
        article_texts.append(article_text)
    
    return "\n\n".join(article_texts)


def summarize_pre_event_expectations(
    ranked_articles: List[Dict],
    company_name: str,
    quarter: str,
    ticker: str = None,
    model: str = None
) -> Dict:
    """
    Summarize market expectations from pre-earnings news articles.
    
    Args:
        ranked_articles: Top N articles from semantic ranking
        company_name: Company name (e.g., "NVIDIA Corporation")
        quarter: Quarter label (e.g., "Q3 FY2026")
        ticker: Optional ticker symbol (e.g., "NVDA")
        model: Optional model override (defaults to env LLM_MODEL or mistral-large-latest)
    
    Returns:
        Dictionary with expectations summary
    
    Example:
        >>> from aifinreport.agents.news_period_analyst import analyze_news_period
        >>> from aifinreport.agents.pre_event_summarizer import summarize_pre_event_expectations
        >>> 
        >>> # Get ranked articles
        >>> result = analyze_news_period(
        ...     ticker="NVDA",
        ...     start_date=pr_time - timedelta(days=7),
        ...     end_date=pr_time,
        ...     quarter="Q3",
        ...     top_n_articles=10
        ... )
        >>> 
        >>> # Summarize expectations
        >>> expectations = summarize_pre_event_expectations(
        ...     ranked_articles=result['ranked_news'],
        ...     company_name="NVIDIA Corporation",
        ...     quarter="Q3 FY2026",
        ...     ticker="NVDA"
        ... )
        >>> 
        >>> print(expectations['expected_results'])
        >>> print(expectations['market_sentiment'])
    """
    if not ranked_articles:
        return {
            'error': 'No articles provided',
            'expected_results': {},
            'expected_guidance': [],
            'key_themes': [],
            'surprise_scenarios': {'positive': [], 'negative': []},
            'market_sentiment': {}
        }
    
    article_count = len(ranked_articles)
    
    print(f"\n📊 Summarizing expectations from {article_count} articles...")
    
    # Format articles for prompt
    articles_text = format_articles_for_prompt(ranked_articles)
    
    # Create prompt
    prompt = EXPECTATIONS_PROMPT.format(
        company_name=company_name,
        quarter=quarter,
        article_count=article_count,
        articles_text=articles_text
    )
    
    # Get LLM settings from environment
    llm_provider = os.getenv('LLM_PROVIDER', 'mistral')
    llm_model = model or os.getenv('LLM_MODEL', 'mistral-large-latest')
    
    print(f"   Using {llm_provider} with model {llm_model}...")
    
    # Call LLM
    if llm_provider == 'mistral':
        try:
            api_key = os.getenv('MISTRAL_API_KEY')
            if not api_key:
                raise ValueError("MISTRAL_API_KEY not found in environment")
            
            client = Mistral(api_key=api_key)
            
            response = client.chat.complete(
                model=llm_model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            expectations = json.loads(result_text)
            
            print(f"   ✅ Expectations summary generated")
            
            # Add metadata
            expectations['_metadata'] = {
                'company_name': company_name,
                'ticker': ticker,
                'quarter': quarter,
                'article_count': article_count,
                'model': llm_model
            }
            
            return expectations
            
        except Exception as e:
            print(f"   ❌ Error calling Mistral API: {e}")
            return {
                'error': str(e),
                'expected_results': {},
                'expected_guidance': [],
                'key_themes': [],
                'surprise_scenarios': {'positive': [], 'negative': []},
                'market_sentiment': {}
            }
    else:
        # Placeholder for other LLM providers
        print(f"   ⚠️  LLM provider '{llm_provider}' not yet supported")
        return {
            'error': f'LLM provider {llm_provider} not implemented',
            'expected_results': {},
            'expected_guidance': [],
            'key_themes': [],
            'surprise_scenarios': {'positive': [], 'negative': []},
            'market_sentiment': {}
        }


def print_expectations_summary(expectations: Dict):
    """
    Pretty-print the expectations summary.
    
    Args:
        expectations: Output from summarize_pre_event_expectations()
    """
    if expectations.get('error'):
        print(f"\n❌ Error: {expectations['error']}")
        return
    
    print("\n" + "="*70)
    print("📊 MARKET EXPECTATIONS SUMMARY")
    print("="*70)
    
    # Metadata
    if '_metadata' in expectations:
        meta = expectations['_metadata']
        print(f"\nCompany: {meta.get('company_name', 'N/A')}")
        if meta.get('ticker'):
            print(f"Ticker: {meta['ticker']}")
        print(f"Quarter: {meta.get('quarter', 'N/A')}")
        print(f"Articles Analyzed: {meta.get('article_count', 0)}")
        print(f"Model: {meta.get('model', 'N/A')}")
    
    # Expected Results
    if expectations.get('expected_results'):
        print(f"\n{'─'*70}")
        print("📈 EXPECTED FINANCIAL RESULTS")
        print(f"{'─'*70}")
        
        for metric, details in expectations['expected_results'].items():
            confidence_emoji = {
                'HIGH': '🟢',
                'MEDIUM': '🟡',
                'LOW': '🔴'
            }.get(details.get('confidence', 'MEDIUM'), '⚪')
            
            print(f"\n{metric.upper()}:")
            print(f"  {confidence_emoji} Expected: {details.get('expected_value', 'N/A')}")
            print(f"  Confidence: {details.get('confidence', 'N/A')} ({details.get('percentage_of_articles', 0)}% of articles)")
            if details.get('context'):
                print(f"  Context: {details['context']}")
    
    # Expected Guidance
    if expectations.get('expected_guidance'):
        print(f"\n{'─'*70}")
        print("🎯 EXPECTED GUIDANCE")
        print(f"{'─'*70}")
        
        for item in expectations['expected_guidance']:
            confidence_emoji = {
                'HIGH': '🟢',
                'MEDIUM': '🟡',
                'LOW': '🔴'
            }.get(item.get('confidence', 'MEDIUM'), '⚪')
            
            print(f"\n{item.get('time_period', 'N/A')}:")
            print(f"  {confidence_emoji} {item.get('guidance_item', 'N/A')}")
            print(f"  Expected: {item.get('expected_content', 'N/A')}")
            print(f"  Why it matters: {item.get('importance', 'N/A')}")
    
    # Key Themes
    if expectations.get('key_themes'):
        print(f"\n{'─'*70}")
        print("💡 KEY THEMES")
        print(f"{'─'*70}")
        
        for theme in expectations['key_themes']:
            sentiment_emoji = {
                'positive': '📈',
                'negative': '📉',
                'neutral': '➡️',
                'mixed': '🔀'
            }.get(theme.get('sentiment', 'neutral'), '⚪')
            
            print(f"\n{sentiment_emoji} {theme.get('theme_name', 'N/A').upper()}")
            print(f"  {theme.get('summary', 'N/A')}")
            print(f"  Mentioned in: {theme.get('article_mentions', 0)} articles")
            
            if theme.get('supporting_points'):
                print(f"  Key points:")
                for point in theme['supporting_points'][:3]:  # Show top 3
                    print(f"    • {point}")
    
    # Surprise Scenarios
    if expectations.get('surprise_scenarios'):
        print(f"\n{'─'*70}")
        print("⚡ POTENTIAL SURPRISES")
        print(f"{'─'*70}")
        
        surprises = expectations['surprise_scenarios']
        
        if surprises.get('positive'):
            print(f"\n✅ POSITIVE SURPRISES:")
            for i, scenario in enumerate(surprises['positive'][:3], 1):  # Top 3
                print(f"\n  {i}. {scenario.get('scenario', 'N/A')}")
                print(f"     Impact: {scenario.get('impact', 'N/A')}")
                print(f"     Likelihood: {scenario.get('likelihood', 'N/A')}")
        
        if surprises.get('negative'):
            print(f"\n⚠️  NEGATIVE SURPRISES:")
            for i, scenario in enumerate(surprises['negative'][:3], 1):  # Top 3
                print(f"\n  {i}. {scenario.get('scenario', 'N/A')}")
                print(f"     Impact: {scenario.get('impact', 'N/A')}")
                print(f"     Likelihood: {scenario.get('likelihood', 'N/A')}")
    
    # Market Sentiment
    if expectations.get('market_sentiment'):
        print(f"\n{'─'*70}")
        print("🎭 MARKET SENTIMENT")
        print(f"{'─'*70}")
        
        sentiment = expectations['market_sentiment']
        
        print(f"\nOverall: {sentiment.get('overall_tone', 'N/A')}")
        print(f"\nConsensus: {sentiment.get('consensus_expectation', 'N/A')}")
        
        if sentiment.get('bull_case'):
            print(f"\n📈 Bull Case: {sentiment['bull_case']}")
        
        if sentiment.get('bear_case'):
            print(f"\n📉 Bear Case: {sentiment['bear_case']}")
        
        if sentiment.get('divergent_views'):
            print(f"\n🔀 Divergent Views: {sentiment['divergent_views']}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    # Example usage
    from datetime import datetime, timezone, timedelta
    from aifinreport.agents.news_period_analyst import analyze_news_period
    
    # Analyze pre-event period
    pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=timezone.utc)
    
    print("Step 1: Analyzing news period and ranking articles...")
    result = analyze_news_period(
        ticker="NVDA",
        start_date=pr_time - timedelta(days=7),
        end_date=pr_time,
        quarter="Q3",
        top_n_articles=10,
        context="Pre-earnings expectations (7 days before press release)"
    )
    
    print("\nStep 2: Summarizing market expectations...")
    expectations = summarize_pre_event_expectations(
        ranked_articles=result['ranked_news'],
        company_name="NVIDIA Corporation",
        quarter="Q3 FY2026",
        ticker="NVDA"
    )
    
    # Print summary
    print_expectations_summary(expectations)
    
    # Optionally save to file
    output_file = "data/expectations_nvda_q3_fy2026.json"
    os.makedirs("data", exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(expectations, f, indent=2, default=str)
    print(f"\n💾 Full expectations saved to: {output_file}")