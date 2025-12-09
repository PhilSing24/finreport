# src/aifinreport/agents/press_release_extractor.py
"""
Press Release Facts Extractor
Extracts actual financial results from earnings press releases.
"""
from typing import Dict
import json
import os
from mistralai import Mistral


# Press release extraction prompt
PRESS_RELEASE_EXTRACTION_PROMPT = """You are extracting ACTUAL RESULTS from a company's earnings press release.

Your task: Extract what was ANNOUNCED in this press release.

---

CONTEXT:
Company: {company_name}
Quarter: {quarter}

---

INPUT:
{press_release_text}

---

YOUR TASK:

Extract the actual results that were announced. Focus on facts and numbers only.

1. REPORTED FINANCIAL RESULTS
   - Extract actual numbers for each metric
   - Specify GAAP vs non-GAAP where applicable
   - Include Q/Q (quarter-over-quarter) and Y/Y (year-over-year) growth rates
   - Extract segment performance (Data Center, Gaming, Professional Visualization, Automotive)

2. FORWARD GUIDANCE PROVIDED
   - What specific guidance did management provide?
   - For which time periods? (next quarter, full year, etc.)
   - Extract ranges and midpoints

3. MANAGEMENT COMMENTARY
   - Key quotes from CEO/CFO
   - Main themes emphasized in the release
   - Language used to describe performance (e.g., "record", "strong", "challenged")

4. NEW ANNOUNCEMENTS
   - Product launches or updates mentioned
   - Partnership announcements
   - Strategic initiatives
   - Any other material news

5. NOTABLE ITEMS
   - One-time charges or gains
   - Changes in accounting or reporting
   - Anything unusual or unexpected highlighted

---

CRITICAL RULES:
- Use EXACT numbers from the press release (e.g., "$57.0 billion" not "$57B")
- Preserve units (billions, millions, percentages)
- Always note if a metric is GAAP or non-GAAP
- Include both absolute values AND growth rates where available
- For guidance, extract the full range if given (e.g., "$65.0 billion, plus or minus 2%")
- Quote management commentary exactly (use quotation marks)

---

OUTPUT FORMAT:

Return valid JSON with this exact structure:

{{
  "reported_results": {{
    "revenue": {{
      "value": "exact number with units",
      "gaap_non_gaap": "GAAP|non-GAAP|both",
      "q_over_q": "percentage or absolute change",
      "y_over_y": "percentage or absolute change",
      "vs_prior_quarter": "comparison value",
      "vs_year_ago": "comparison value"
    }},
    "eps": {{
      "gaap": "value if reported",
      "non_gaap": "value if reported",
      "q_over_q": "percentage change",
      "y_over_y": "percentage change"
    }},
    "gross_margin": {{
      "gaap": "percentage",
      "non_gaap": "percentage",
      "q_over_q_change": "basis points or percentage points",
      "y_over_y_change": "basis points or percentage points"
    }},
    "operating_income": {{
      "gaap": "value",
      "non_gaap": "value",
      "q_over_q": "percentage",
      "y_over_y": "percentage"
    }},
    "net_income": {{
      "gaap": "value",
      "non_gaap": "value",
      "q_over_q": "percentage",
      "y_over_y": "percentage"
    }}
  }},
  
  "segment_performance": [
    {{
      "segment_name": "name (e.g., Data Center)",
      "revenue": "value with units",
      "q_over_q": "percentage",
      "y_over_y": "percentage",
      "notes": "any special commentary about this segment"
    }}
  ],
  
  "guidance_provided": [
    {{
      "time_period": "which period (e.g., Q4 FY2026)",
      "metric": "what is being guided (revenue, margin, etc.)",
      "guidance_value": "the guidance provided (ranges, percentages)",
      "context": "any additional context or assumptions stated"
    }}
  ],
  
  "management_commentary": [
    {{
      "speaker": "CEO|CFO|other",
      "quote": "exact quote from press release",
      "theme": "what topic this addresses"
    }}
  ],
  
  "new_announcements": [
    {{
      "type": "product|partnership|strategic|other",
      "announcement": "description of what was announced",
      "significance": "why this matters based on press release emphasis"
    }}
  ],
  
  "notable_items": [
    "any one-time items, unusual charges, or special mentions"
  ]
}}

---

IMPORTANT:
- Extract ONLY facts stated in the press release
- Use exact numbers and quotes
- Do not infer or calculate anything not explicitly stated
- If a metric is not mentioned, omit it from the output
- Be precise with terminology (GAAP vs non-GAAP, revenue vs income, etc.)
"""


def extract_press_release_facts(
    call_id: str,
    company_name: str = None,
    quarter: str = None,
    model: str = None
) -> Dict:
    """
    Extract actual financial results from earnings press release.
    
    Args:
        call_id: Earnings call ID (e.g., "earnings:nvda:q3-fy2026")
        company_name: Company name (e.g., "NVIDIA Corporation")
        quarter: Quarter label (e.g., "Q3 FY2026")
        model: Optional model override (defaults to env LLM_MODEL)
    
    Returns:
        Dictionary with actual results
    
    Example:
        >>> from aifinreport.agents.press_release_extractor import extract_press_release_facts
        >>> 
        >>> actuals = extract_press_release_facts(
        ...     call_id="earnings:nvda:q3-fy2026",
        ...     company_name="NVIDIA Corporation",
        ...     quarter="Q3 FY2026"
        ... )
        >>> 
        >>> print(actuals['reported_results']['revenue'])
        >>> print(actuals['guidance_provided'])
    """
    # Import here to avoid circular dependency
    from aifinreport.tools.database_tools import get_press_release
    
    print(f"\n📄 Extracting facts from press release...")
    print(f"   Call ID: {call_id}")
    
    # Retrieve press release from database
    try:
        pr = get_press_release(call_id)
        if not pr:
            return {
                'error': f'Press release not found for {call_id}',
                'reported_results': {},
                'segment_performance': [],
                'guidance_provided': [],
                'management_commentary': [],
                'new_announcements': [],
                'notable_items': []
            }
        
        press_release_text = pr['full_body']
        
        # Use metadata from press release if not provided
        if not company_name:
            # Try to extract from title or use ticker
            company_name = pr.get('title', '').split(' ')[0] + " Corporation"
        
        if not quarter:
            # Try to extract from title
            title = pr.get('title', '')
            if 'Third Quarter' in title or 'Q3' in title:
                quarter = "Q3"
            elif 'Second Quarter' in title or 'Q2' in title:
                quarter = "Q2"
            elif 'First Quarter' in title or 'Q1' in title:
                quarter = "Q1"
            elif 'Fourth Quarter' in title or 'Q4' in title:
                quarter = "Q4"
        
        print(f"   Company: {company_name}")
        print(f"   Quarter: {quarter}")
        print(f"   Press release length: {len(press_release_text):,} characters")
        
    except Exception as e:
        print(f"   ❌ Error retrieving press release: {e}")
        return {
            'error': str(e),
            'reported_results': {},
            'segment_performance': [],
            'guidance_provided': [],
            'management_commentary': [],
            'new_announcements': [],
            'notable_items': []
        }
    
    # Create prompt
    prompt = PRESS_RELEASE_EXTRACTION_PROMPT.format(
        company_name=company_name,
        quarter=quarter,
        press_release_text=press_release_text
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
            actuals = json.loads(result_text)
            
            print(f"   ✅ Facts extracted successfully")
            
            # Add metadata
            actuals['_metadata'] = {
                'call_id': call_id,
                'company_name': company_name,
                'quarter': quarter,
                'press_release_date': pr.get('published_utc'),
                'model': llm_model
            }
            
            return actuals
            
        except Exception as e:
            print(f"   ❌ Error calling LLM: {e}")
            return {
                'error': str(e),
                'reported_results': {},
                'segment_performance': [],
                'guidance_provided': [],
                'management_commentary': [],
                'new_announcements': [],
                'notable_items': []
            }
    else:
        print(f"   ⚠️  LLM provider '{llm_provider}' not yet supported")
        return {
            'error': f'LLM provider {llm_provider} not implemented',
            'reported_results': {},
            'segment_performance': [],
            'guidance_provided': [],
            'management_commentary': [],
            'new_announcements': [],
            'notable_items': []
        }


def print_actuals_summary(actuals: Dict):
    """
    Pretty-print the extracted actuals.
    
    Args:
        actuals: Output from extract_press_release_facts()
    """
    if actuals.get('error'):
        print(f"\n❌ Error: {actuals['error']}")
        return
    
    print("\n" + "="*70)
    print("📄 PRESS RELEASE ACTUAL RESULTS")
    print("="*70)
    
    # Metadata
    if '_metadata' in actuals:
        meta = actuals['_metadata']
        print(f"\nCompany: {meta.get('company_name', 'N/A')}")
        print(f"Quarter: {meta.get('quarter', 'N/A')}")
        if meta.get('press_release_date'):
            pr_date = meta['press_release_date']
            date_str = pr_date.strftime('%Y-%m-%d %H:%M UTC') if hasattr(pr_date, 'strftime') else str(pr_date)
            print(f"Press Release Date: {date_str}")
        print(f"Model: {meta.get('model', 'N/A')}")
    
    # Reported Results
    if actuals.get('reported_results'):
        print(f"\n{'─'*70}")
        print("💰 REPORTED FINANCIAL RESULTS")
        print(f"{'─'*70}")
        
        results = actuals['reported_results']
        
        if 'revenue' in results:
            rev = results['revenue']
            print(f"\n📊 REVENUE: {rev.get('value', 'N/A')}")
            if rev.get('q_over_q'):
                print(f"   Q/Q: {rev['q_over_q']}")
            if rev.get('y_over_y'):
                print(f"   Y/Y: {rev['y_over_y']}")
        
        if 'eps' in results:
            eps = results['eps']
            print(f"\n💵 EPS:")
            if eps.get('gaap'):
                print(f"   GAAP: {eps['gaap']}")
            if eps.get('non_gaap'):
                print(f"   Non-GAAP: {eps['non_gaap']}")
            if eps.get('y_over_y'):
                print(f"   Y/Y: {eps['y_over_y']}")
        
        if 'gross_margin' in results:
            margin = results['gross_margin']
            print(f"\n📈 GROSS MARGIN:")
            if margin.get('gaap'):
                print(f"   GAAP: {margin['gaap']}")
            if margin.get('non_gaap'):
                print(f"   Non-GAAP: {margin['non_gaap']}")
    
    # Segment Performance
    if actuals.get('segment_performance'):
        print(f"\n{'─'*70}")
        print("📊 SEGMENT PERFORMANCE")
        print(f"{'─'*70}")
        
        for segment in actuals['segment_performance']:
            print(f"\n{segment.get('segment_name', 'N/A')}:")
            print(f"   Revenue: {segment.get('revenue', 'N/A')}")
            if segment.get('q_over_q'):
                print(f"   Q/Q: {segment['q_over_q']}")
            if segment.get('y_over_y'):
                print(f"   Y/Y: {segment['y_over_y']}")
            if segment.get('notes'):
                print(f"   Notes: {segment['notes']}")
    
    # Guidance
    if actuals.get('guidance_provided'):
        print(f"\n{'─'*70}")
        print("🎯 FORWARD GUIDANCE")
        print(f"{'─'*70}")
        
        for guide in actuals['guidance_provided']:
            print(f"\n{guide.get('time_period', 'N/A')} - {guide.get('metric', 'N/A')}:")
            print(f"   Guidance: {guide.get('guidance_value', 'N/A')}")
            if guide.get('context'):
                print(f"   Context: {guide['context']}")
    
    # Management Commentary
    if actuals.get('management_commentary'):
        print(f"\n{'─'*70}")
        print("💬 MANAGEMENT COMMENTARY")
        print(f"{'─'*70}")
        
        for comment in actuals['management_commentary'][:3]:  # Show top 3
            speaker = comment.get('speaker', 'Management')
            theme = comment.get('theme', '')
            quote = comment.get('quote', 'N/A')
            
            print(f"\n{speaker}" + (f" on {theme}" if theme else "") + ":")
            print(f'   "{quote}"')
    
    # New Announcements
    if actuals.get('new_announcements'):
        print(f"\n{'─'*70}")
        print("📢 NEW ANNOUNCEMENTS")
        print(f"{'─'*70}")
        
        for announcement in actuals['new_announcements'][:5]:  # Show top 5
            ann_type = announcement.get('type', 'Other')
            text = announcement.get('announcement', 'N/A')
            
            type_emoji = {
                'product': '🔧',
                'partnership': '🤝',
                'strategic': '🎯',
                'other': '📌'
            }.get(ann_type.lower(), '📌')
            
            print(f"\n{type_emoji} {text}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    # Example usage
    import sys
    
    call_id = sys.argv[1] if len(sys.argv) > 1 else "earnings:nvda:q3-fy2026"
    
    print(f"Extracting press release facts for: {call_id}")
    
    actuals = extract_press_release_facts(
        call_id=call_id,
        company_name="NVIDIA Corporation",
        quarter="Q3 FY2026"
    )
    
    # Print summary
    print_actuals_summary(actuals)
    
    # Save to file
    output_file = f"data/actuals_{call_id.replace('earnings:', '').replace(':', '_')}.json"
    os.makedirs("data", exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(actuals, f, indent=2, default=str)
    print(f"\n💾 Full actuals saved to: {output_file}")