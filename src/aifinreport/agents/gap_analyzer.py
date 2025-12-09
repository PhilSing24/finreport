# src/aifinreport/agents/gap_analyzer.py
"""
Gap Analyzer
Compares market expectations vs actual results to identify surprises.
"""
from typing import Dict
import json
import os
from mistralai import Mistral
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Gap analysis prompt
GAP_ANALYSIS_PROMPT = """You are a financial analyst comparing market EXPECTATIONS vs ACTUAL RESULTS from an earnings announcement.

Your task: Identify surprises (beats and misses) and assess their market impact.

---

CONTEXT:
Company: {company_name}
Quarter: {quarter}

---

MARKET EXPECTATIONS (from analyst coverage before earnings):
{expectations_json}

---

ACTUAL RESULTS (from press release):
{actuals_json}

---

YOUR TASK:

Compare expectations vs actuals to identify material surprises.

1. METRIC-BY-METRIC COMPARISON
   - For each key metric, compare expected vs actual
   - Calculate the surprise (difference in $ and %)
   - Determine significance: HIGH (>5% surprise), MEDIUM (2-5%), LOW (<2%)
   - Note if the metric was widely expected (HIGH confidence) vs speculative (LOW confidence)

2. POSITIVE SURPRISES (Beats)
   - Which metrics exceeded expectations?
   - By how much?
   - Which are most significant for stock valuation?
   - Were these anticipated by any analysts?

3. NEGATIVE SURPRISES (Misses)
   - Which metrics fell short of expectations?
   - By how much?
   - Which are most concerning for investors?
   - Any explanations provided in the press release?

4. NEW INFORMATION NOT ANTICIPATED
   - What was announced that wasn't discussed in pre-earnings coverage?
   - New products, partnerships, or strategic moves
   - Management commentary that changes the narrative
   - Guidance that differs from consensus

5. MARKET IMPACT ASSESSMENT
   - Overall verdict: Strong beat / Mixed / Disappointment
   - Expected stock reaction: magnitude and direction
   - Key drivers of the reaction
   - What will analysts focus on in the Q&A?

---

CRITICAL RULES:
- Be precise with numbers (exact $ amounts and percentages)
- Consider the CONFIDENCE level of expectations
  * HIGH confidence expectations that are beaten = bigger surprise
  * LOW confidence expectations = less meaningful if beaten/missed
- Distinguish between GAAP and non-GAAP where relevant
- For guidance, compare to consensus expectations if mentioned
- Flag "new information" that wasn't in the pre-event discussion
- Be objective - report facts, not opinions

---

OUTPUT FORMAT:

Return valid JSON with this exact structure:

{{
  "positive_surprises": [
    {{
      "metric": "name of metric (e.g., Revenue)",
      "expected": "what was expected with source confidence",
      "actual": "what was reported",
      "surprise_amount": "$ difference",
      "surprise_percentage": "% difference",
      "significance": "HIGH|MEDIUM|LOW",
      "explanation": "why this matters",
      "expectation_confidence": "confidence level from expectations (HIGH|MEDIUM|LOW)"
    }}
  ],
  
  "negative_surprises": [
    {{
      "metric": "name of metric",
      "expected": "what was expected",
      "actual": "what was reported",
      "miss_amount": "$ difference",
      "miss_percentage": "% difference",
      "significance": "HIGH|MEDIUM|LOW",
      "explanation": "why this is concerning",
      "expectation_confidence": "confidence level from expectations"
    }}
  ],
  
  "in_line_results": [
    {{
      "metric": "name of metric",
      "expected": "what was expected",
      "actual": "what was reported",
      "variance": "small difference if any"
    }}
  ],
  
  "guidance_analysis": {{
    "q4_revenue_vs_expectations": "comparison if expectations mentioned Q4",
    "guidance_surprise": "beat|in-line|miss|not-discussed",
    "significance": "how important is this guidance"
  }},
  
  "new_information_not_anticipated": [
    {{
      "type": "product|partnership|commentary|strategic|other",
      "information": "what was announced",
      "significance": "HIGH|MEDIUM|LOW",
      "potential_impact": "how this might affect stock"
    }}
  ],
  
  "narrative_changes": [
    "any shifts in management tone or themes vs pre-event coverage"
  ],
  
  "market_impact_assessment": {{
    "overall_verdict": "strong beat|slight beat|in-line|slight miss|significant miss|mixed",
    "expected_stock_reaction": "direction and magnitude (e.g., +4-6%, -2-3%)",
    "confidence_in_prediction": "HIGH|MEDIUM|LOW",
    "key_reaction_drivers": [
      "what will drive the stock movement"
    ],
    "bull_take": "optimistic interpretation of results",
    "bear_take": "pessimistic interpretation of results",
    "questions_for_qa": [
      "what analysts will likely ask about in earnings call"
    ]
  }}
}}

---

IMPORTANT:
- Focus on MATERIAL differences that could move the stock
- Consider both the size of the surprise AND the confidence in expectations
- A 10% beat on a LOW confidence metric matters less than 3% beat on HIGH confidence
- Distinguish between "surprising but positive" vs "expected and positive"
- Be specific about market impact - use percentages for expected reactions
"""


def compare_expectations_vs_actuals(
    expectations: Dict,
    actuals: Dict,
    company_name: str = None,
    quarter: str = None,
    model: str = None
) -> Dict:
    """
    Compare market expectations vs actual results to identify surprises.
    
    Args:
        expectations: Output from summarize_pre_event_expectations()
        actuals: Output from extract_press_release_facts()
        company_name: Company name (e.g., "NVIDIA Corporation")
        quarter: Quarter label (e.g., "Q3 FY2026")
        model: Optional model override (defaults to env LLM_MODEL)
    
    Returns:
        Dictionary with gap analysis
    
    Example:
        >>> from aifinreport.agents.pre_event_summarizer import summarize_pre_event_expectations
        >>> from aifinreport.agents.press_release_extractor import extract_press_release_facts
        >>> from aifinreport.agents.gap_analyzer import compare_expectations_vs_actuals
        >>> 
        >>> # Load expectations
        >>> with open('data/expectations_nvda_q3_fy2026.json') as f:
        ...     expectations = json.load(f)
        >>> 
        >>> # Extract actuals
        >>> actuals = extract_press_release_facts("earnings:nvda:q3-fy2026")
        >>> 
        >>> # Compare
        >>> gap_analysis = compare_expectations_vs_actuals(
        ...     expectations=expectations,
        ...     actuals=actuals,
        ...     company_name="NVIDIA Corporation",
        ...     quarter="Q3 FY2026"
        ... )
        >>> 
        >>> print(gap_analysis['positive_surprises'])
        >>> print(gap_analysis['market_impact_assessment'])
    """
    if expectations.get('error') or actuals.get('error'):
        return {
            'error': 'Cannot compare - missing expectations or actuals',
            'positive_surprises': [],
            'negative_surprises': [],
            'market_impact_assessment': {}
        }
    
    # Extract metadata
    if not company_name:
        company_name = (
            expectations.get('_metadata', {}).get('company_name') or
            actuals.get('_metadata', {}).get('company_name') or
            "Company"
        )
    
    if not quarter:
        quarter = (
            expectations.get('_metadata', {}).get('quarter') or
            actuals.get('_metadata', {}).get('quarter') or
            "Quarter"
        )
    
    print(f"\n🔍 Comparing expectations vs actuals...")
    print(f"   Company: {company_name}")
    print(f"   Quarter: {quarter}")
    
    # Convert to JSON strings for LLM
    expectations_json = json.dumps(expectations, indent=2, default=str)
    actuals_json = json.dumps(actuals, indent=2, default=str)
    
    # Create prompt
    prompt = GAP_ANALYSIS_PROMPT.format(
        company_name=company_name,
        quarter=quarter,
        expectations_json=expectations_json,
        actuals_json=actuals_json
    )
    
    # Get LLM settings
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
            gap_analysis = json.loads(result_text)
            
            print(f"   ✅ Gap analysis completed")
            
            # Add metadata
            gap_analysis['_metadata'] = {
                'company_name': company_name,
                'quarter': quarter,
                'expectations_article_count': expectations.get('_metadata', {}).get('article_count'),
                'model': llm_model
            }
            
            return gap_analysis
            
        except Exception as e:
            print(f"   ❌ Error calling LLM: {e}")
            return {
                'error': str(e),
                'positive_surprises': [],
                'negative_surprises': [],
                'market_impact_assessment': {}
            }
    else:
        print(f"   ⚠️  LLM provider '{llm_provider}' not yet supported")
        return {
            'error': f'LLM provider {llm_provider} not implemented',
            'positive_surprises': [],
            'negative_surprises': [],
            'market_impact_assessment': {}
        }


def print_gap_analysis_summary(gap_analysis: Dict):
    """
    Pretty-print the gap analysis.
    
    Args:
        gap_analysis: Output from compare_expectations_vs_actuals()
    """
    if gap_analysis.get('error'):
        print(f"\n❌ Error: {gap_analysis['error']}")
        return
    
    print("\n" + "="*70)
    print("⚡ GAP ANALYSIS: EXPECTATIONS VS ACTUALS")
    print("="*70)
    
    # Metadata
    if '_metadata' in gap_analysis:
        meta = gap_analysis['_metadata']
        print(f"\nCompany: {meta.get('company_name', 'N/A')}")
        print(f"Quarter: {meta.get('quarter', 'N/A')}")
        if meta.get('expectations_article_count'):
            print(f"Based on: {meta['expectations_article_count']} analyst articles")
        print(f"Model: {meta.get('model', 'N/A')}")
    
    # Positive Surprises
    if gap_analysis.get('positive_surprises'):
        print(f"\n{'─'*70}")
        print("✅ POSITIVE SURPRISES (Beats)")
        print(f"{'─'*70}")
        
        for surprise in gap_analysis['positive_surprises']:
            sig_emoji = {
                'HIGH': '🔥',
                'MEDIUM': '📈',
                'LOW': '✓'
            }.get(surprise.get('significance', 'LOW'), '✓')
            
            conf_emoji = {
                'HIGH': '🟢',
                'MEDIUM': '🟡',
                'LOW': '🔴'
            }.get(surprise.get('expectation_confidence', 'MEDIUM'), '⚪')
            
            print(f"\n{sig_emoji} {surprise.get('metric', 'N/A').upper()} - {surprise.get('significance', 'N/A')} significance")
            print(f"   Expected: {surprise.get('expected', 'N/A')} {conf_emoji}")
            print(f"   Actual:   {surprise.get('actual', 'N/A')}")
            print(f"   Beat by:  {surprise.get('surprise_amount', 'N/A')} ({surprise.get('surprise_percentage', 'N/A')})")
            if surprise.get('explanation'):
                print(f"   Impact:   {surprise['explanation']}")
    
    # Negative Surprises
    if gap_analysis.get('negative_surprises'):
        print(f"\n{'─'*70}")
        print("⚠️  NEGATIVE SURPRISES (Misses)")
        print(f"{'─'*70}")
        
        for miss in gap_analysis['negative_surprises']:
            sig_emoji = {
                'HIGH': '🔴',
                'MEDIUM': '📉',
                'LOW': '⚠'
            }.get(miss.get('significance', 'LOW'), '⚠')
            
            print(f"\n{sig_emoji} {miss.get('metric', 'N/A').upper()} - {miss.get('significance', 'N/A')} significance")
            print(f"   Expected: {miss.get('expected', 'N/A')}")
            print(f"   Actual:   {miss.get('actual', 'N/A')}")
            print(f"   Missed by: {miss.get('miss_amount', 'N/A')} ({miss.get('miss_percentage', 'N/A')})")
            if miss.get('explanation'):
                print(f"   Concern:  {miss['explanation']}")
    
    # In-Line Results
    if gap_analysis.get('in_line_results'):
        print(f"\n{'─'*70}")
        print("➡️  IN-LINE RESULTS")
        print(f"{'─'*70}")
        
        for item in gap_analysis['in_line_results'][:3]:  # Show top 3
            print(f"\n• {item.get('metric', 'N/A')}")
            print(f"  Expected: {item.get('expected', 'N/A')}")
            print(f"  Actual:   {item.get('actual', 'N/A')}")
    
    # Guidance Analysis
    if gap_analysis.get('guidance_analysis'):
        guide = gap_analysis['guidance_analysis']
        if guide.get('guidance_surprise') and guide['guidance_surprise'] != 'not-discussed':
            print(f"\n{'─'*70}")
            print("🎯 GUIDANCE ANALYSIS")
            print(f"{'─'*70}")
            
            surprise_emoji = {
                'beat': '📈',
                'in-line': '➡️',
                'miss': '📉'
            }.get(guide.get('guidance_surprise', 'in-line'), '⚪')
            
            print(f"\n{surprise_emoji} Guidance: {guide.get('guidance_surprise', 'N/A').upper()}")
            if guide.get('q4_revenue_vs_expectations'):
                print(f"   {guide['q4_revenue_vs_expectations']}")
            if guide.get('significance'):
                print(f"   Significance: {guide['significance']}")
    
    # New Information
    if gap_analysis.get('new_information_not_anticipated'):
        print(f"\n{'─'*70}")
        print("🆕 NEW INFORMATION NOT ANTICIPATED")
        print(f"{'─'*70}")
        
        for item in gap_analysis['new_information_not_anticipated'][:5]:  # Top 5
            sig_emoji = {
                'HIGH': '🔥',
                'MEDIUM': '📌',
                'LOW': '💡'
            }.get(item.get('significance', 'MEDIUM'), '💡')
            
            type_label = item.get('type', 'other').upper()
            
            print(f"\n{sig_emoji} [{type_label}] {item.get('information', 'N/A')}")
            if item.get('potential_impact'):
                print(f"   Impact: {item['potential_impact']}")
    
    # Narrative Changes
    if gap_analysis.get('narrative_changes'):
        print(f"\n{'─'*70}")
        print("📝 NARRATIVE CHANGES")
        print(f"{'─'*70}")
        
        for change in gap_analysis['narrative_changes'][:3]:
            print(f"\n• {change}")
    
    # Market Impact Assessment
    if gap_analysis.get('market_impact_assessment'):
        print(f"\n{'─'*70}")
        print("📊 MARKET IMPACT ASSESSMENT")
        print(f"{'─'*70}")
        
        impact = gap_analysis['market_impact_assessment']
        
        verdict = impact.get('overall_verdict', 'N/A')
        verdict_emoji = {
            'strong beat': '🚀',
            'slight beat': '📈',
            'in-line': '➡️',
            'slight miss': '📉',
            'significant miss': '🔴',
            'mixed': '🔀'
        }.get(verdict.lower(), '⚪')
        
        print(f"\n{verdict_emoji} Overall Verdict: {verdict.upper()}")
        
        if impact.get('expected_stock_reaction'):
            print(f"\n💹 Expected Stock Reaction: {impact['expected_stock_reaction']}")
            if impact.get('confidence_in_prediction'):
                print(f"   Confidence: {impact['confidence_in_prediction']}")
        
        if impact.get('key_reaction_drivers'):
            print(f"\n🔑 Key Reaction Drivers:")
            for driver in impact['key_reaction_drivers'][:5]:
                print(f"   • {driver}")
        
        if impact.get('bull_take'):
            print(f"\n📈 Bull Take:")
            print(f"   {impact['bull_take']}")
        
        if impact.get('bear_take'):
            print(f"\n📉 Bear Take:")
            print(f"   {impact['bear_take']}")
        
        if impact.get('questions_for_qa'):
            print(f"\n❓ Expected Questions for Q&A:")
            for q in impact['questions_for_qa'][:3]:
                print(f"   • {q}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    # Example usage
    import sys
    
    call_id = sys.argv[1] if len(sys.argv) > 1 else "earnings:nvda:q3-fy2026"
    
    print(f"Running gap analysis for: {call_id}")
    
    # Load expectations
    expectations_file = f"data/expectations_{call_id.replace('earnings:', '').replace(':', '_')}.json"
    try:
        with open(expectations_file, 'r') as f:
            expectations = json.load(f)
        print(f"✅ Loaded expectations from: {expectations_file}")
    except FileNotFoundError:
        print(f"❌ Expectations file not found: {expectations_file}")
        print(f"   Run pre_event_summarizer first!")
        sys.exit(1)
    
    # Load actuals
    actuals_file = f"data/actuals_{call_id.replace('earnings:', '').replace(':', '_')}.json"
    try:
        with open(actuals_file, 'r') as f:
            actuals = json.load(f)
        print(f"✅ Loaded actuals from: {actuals_file}")
    except FileNotFoundError:
        print(f"❌ Actuals file not found: {actuals_file}")
        print(f"   Run press_release_extractor first!")
        sys.exit(1)
    
    # Compare
    gap_analysis = compare_expectations_vs_actuals(
        expectations=expectations,
        actuals=actuals,
        company_name="NVIDIA Corporation",
        quarter="Q3 FY2026"
    )
    
    # Print summary
    print_gap_analysis_summary(gap_analysis)
    
    # Save to file
    output_file = f"data/gap_analysis_{call_id.replace('earnings:', '').replace(':', '_')}.json"
    os.makedirs("data", exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(gap_analysis, f, indent=2, default=str)
    print(f"\n💾 Full gap analysis saved to: {output_file}")