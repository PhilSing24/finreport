# src/aifinreport/agents/earnings_analyst.py
"""
Earnings Impact Analyst Agent
Analyzes earnings calls and generates investment briefs.
"""
from typing import TypedDict, Annotated, List, Dict, Optional
from datetime import datetime


class AgentState(TypedDict):
    """
    State tracked by the agent throughout analysis.
    This is the agent's "working memory".
    """
    # Input
    call_id: str
    
    # Call metadata
    ticker: str
    fiscal_quarter: str
    fiscal_year: int
    call_date: str
    call_start_utc: datetime
    
    # Content from database
    prepared_remarks: List[Dict]
    qa_section: List[Dict]
    news_pre_call: List[Dict]
    news_post_call: List[Dict]
    
    # Market data
    stock_prices: List[Dict]
    
    # Analysis results (populated by LLM)
    key_metrics: Optional[Dict]
    management_tone: Optional[str]
    analyst_concerns: Optional[List[str]]
    market_reaction: Optional[Dict]
    
    # Final output
    report: Optional[str]
    
    # Control flow
    current_step: str
    errors: List[str]


def create_initial_state(call_id: str) -> AgentState:
    """
    Create initial agent state with just the call_id.
    All other fields will be populated as the agent runs.
    """
    return AgentState(
        call_id=call_id,
        ticker="",
        fiscal_quarter="",
        fiscal_year=0,
        call_date="",
        call_start_utc=None,
        prepared_remarks=[],
        qa_section=[],
        news_pre_call=[],
        news_post_call=[],
        stock_prices=[],
        key_metrics=None,
        management_tone=None,
        analyst_concerns=None,
        market_reaction=None,
        report=None,
        current_step="start",
        errors=[]
    )

# Add these imports at the top
from aifinreport.tools.database_tools import (
    get_earnings_call,
    get_prepared_remarks,
    get_qa_section,
    search_news_around_call
)
from aifinreport.tools.market_data_tools import fetch_ohlc_bars
from datetime import timedelta


# Node 1: Load Call Info
def load_call_info(state: AgentState) -> AgentState:
    """
    Load earnings call metadata from database.
    """
    print(f"\n📋 Loading call info for {state['call_id']}...")
    
    try:
        call = get_earnings_call(state['call_id'])
        
        state['ticker'] = call['ticker']
        state['fiscal_quarter'] = call['fiscal_quarter']
        state['fiscal_year'] = call['fiscal_year']
        state['call_date'] = call['call_date']
        state['call_start_utc'] = call['call_start_utc']
        state['current_step'] = "load_content"
        
        print(f"✅ Loaded: {call['ticker']} {call['fiscal_quarter']} {call['fiscal_year']}")
        
    except Exception as e:
        state['errors'].append(f"Failed to load call info: {e}")
        state['current_step'] = "error"
    
    return state


# Node 2: Load Content
def load_content(state: AgentState) -> AgentState:
    """
    Load prepared remarks, Q&A, and news from database.
    """
    print(f"\n📚 Loading content...")
    
    try:
        # Get prepared remarks
        state['prepared_remarks'] = get_prepared_remarks(state['call_id'])
        print(f"✅ Loaded {len(state['prepared_remarks'])} prepared remarks")
        
        # Get Q&A
        state['qa_section'] = get_qa_section(state['call_id'])
        print(f"✅ Loaded {len(state['qa_section'])} Q&A interventions")
        
        # Get pre-call news
        state['news_pre_call'] = search_news_around_call(
            state['call_id'], 
            time_window="pre-call",
            limit=20
        )
        print(f"✅ Loaded {len(state['news_pre_call'])} pre-call news articles")
        
        # Get post-call news
        state['news_post_call'] = search_news_around_call(
            state['call_id'],
            time_window="post-24h",
            limit=20
        )
        print(f"✅ Loaded {len(state['news_post_call'])} post-call news articles")
        
        state['current_step'] = "fetch_prices"
        
    except Exception as e:
        state['errors'].append(f"Failed to load content: {e}")
        state['current_step'] = "error"
    
    return state


# Node 3: Fetch Prices
def fetch_prices(state: AgentState) -> AgentState:
    """
    Fetch stock prices around earnings call.
    """
    print(f"\n📈 Fetching stock prices...")
    
    try:
        bars = fetch_ohlc_bars(
            ticker=state['ticker'],
            start_time=state['call_start_utc'] - timedelta(hours=1),
            end_time=state['call_start_utc'] + timedelta(hours=3),
            interval="5min"
        )
        
        state['stock_prices'] = bars
        print(f"✅ Fetched {len(bars)} price bars")
        
        if bars:
            price_change = bars[-1]['close'] - bars[0]['close']
            price_change_pct = (price_change / bars[0]['close']) * 100
            print(f"   Price movement: ${bars[0]['close']:.2f} → ${bars[-1]['close']:.2f} ({price_change_pct:+.2f}%)")
        
        state['current_step'] = "analyze"
        
    except Exception as e:
        state['errors'].append(f"Failed to fetch prices: {e}")
        # Non-critical, continue anyway
        state['current_step'] = "analyze"
    
    return state


# Node 4: Analyze (Placeholder for now)
def analyze(state: AgentState) -> AgentState:
    """
    Analyze all data and generate insights.
    This is where LLM analysis will happen.
    """
    print(f"\n🤖 Analyzing data...")
    
    # For now, just placeholder
    state['key_metrics'] = {"status": "Analysis pending - LLM integration next"}
    state['current_step'] = "generate_report"
    
    return state


# Node 5: Generate Report (Placeholder)
def generate_report(state: AgentState) -> AgentState:
    """
    Generate final markdown report.
    """
    print(f"\n📝 Generating report...")
    
    # Placeholder report
    report = f"""# {state['ticker']} {state['fiscal_quarter']} FY{state['fiscal_year']} Earnings Analysis

## Data Collected
- Prepared remarks: {len(state['prepared_remarks'])} interventions
- Q&A section: {len(state['qa_section'])} interventions
- Pre-call news: {len(state['news_pre_call'])} articles
- Post-call news: {len(state['news_post_call'])} articles
- Price bars: {len(state['stock_prices'])} bars

## Next Steps
LLM analysis will be added to extract insights and generate comprehensive report.
"""
    
    state['report'] = report
    state['current_step'] = "complete"
    
    print(f"✅ Report generated")
    
    return state


# Simple linear execution for now
def run_agent(call_id: str) -> AgentState:
    """
    Run the earnings analyst agent.
    """
    print("=" * 70)
    print("🤖 Starting Earnings Impact Analyst Agent")
    print("=" * 70)
    
    # Create initial state
    state = create_initial_state(call_id)
    
    # Execute nodes in sequence
    state = load_call_info(state)
    
    if state['current_step'] != "error":
        state = load_content(state)
    
    if state['current_step'] != "error":
        state = fetch_prices(state)
    
    if state['current_step'] != "error":
        state = analyze(state)
    
    if state['current_step'] != "error":
        state = generate_report(state)
    
    print("\n" + "=" * 70)
    if state['errors']:
        print("⚠️  Agent completed with errors:")
        for error in state['errors']:
            print(f"   - {error}")
    else:
        print("✅ Agent completed successfully!")
    print("=" * 70)
    
    return state

if __name__ == "__main__":
    # Test running the full agent
    state = run_agent("earnings:nvda:q2-fy2026")
    
    # Print report
    if state['report']:
        print("\n" + "=" * 70)
        print("GENERATED REPORT:")
        print("=" * 70)
        print(state['report'])