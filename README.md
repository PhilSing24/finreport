# AIFinReport - AI-Powered Financial Analysis System

An **agentic AI application** that uses autonomous AI agents to analyze financial data. The system independently processes earnings call transcripts, correlates news sentiment, and tracks market movements to generate comprehensive investment insights.

## 🎯 Overview

AIFinReport automatically analyzes earnings calls by:

- Processing detailed earnings call transcripts (prepared remarks + Q&A + closing)
- Fetching 3-phase stock price data around earnings events
- Correlating with news sentiment before and after calls
- Generating actionable investment briefs using AI agents

## ✨ Features

### Data Ingestion
- **News Articles**: Automated ingestion from Tiingo API
- **Earnings Calls**: Parse structured transcripts with:
  - Speaker attribution and roles
  - Precise UTC timestamps
  - Q&A segmentation (questions, answers, analyst firms)
  - Closing remarks
- **Stock Prices**: Real-time and historical OHLC data from Massive.com API
  - 3-phase analysis (pre-event, event, post-event)
  - Multiple intervals (1min, 5min, 15min, 1hour, 1day)
  - Timezone-aware (UTC) with Singapore (UTC+8) support

### AI Agent Analysis
- **Earnings Impact Analyst**: Autonomous agent that analyzes earnings calls
  - Extracts key financial metrics from management remarks
  - Identifies analyst concerns from Q&A sessions
  - Correlates market reaction with call content
  - Synthesizes news sentiment around earnings events

### Database
PostgreSQL with structured storage for:
- Earnings call metadata and full transcripts
- Timestamped interventions (speaker, role, content)
- Q&A segmentation with question-answer linking
- News articles with ticker associations
- Time-series ready for price correlation
- **All timestamps in UTC** (timestamptz)

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
├─────────────┬──────────────────┬────────────────────────┤
│  Tiingo API │  Manual Entry    │    Massive.com API     │
│   (News)    │  (Transcripts)   │   (Stock Prices)       │
└──────┬──────┴────────┬─────────┴──────────┬─────────────┘
       │               │                    │
       ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│              Ingestion Layer                             │
│  • tiingo.py          • earnings_parser.py               │
│  • fetchers.py        • earnings_storage.py              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                PostgreSQL Database                       │
│  • earnings_calls (timestamptz)                          │
│  • call_interventions (full capture including closing)   │
│  • news_raw / news_normalized                            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent Tools                            │
│  • database_tools.py (8 query functions)                 │
│  • market_data_tools.py (3-phase price analysis)         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│            Earnings Impact Analyst Agent                 │
│  • Load call metadata    • Fetch 3-phase prices          │
│  • Extract key metrics   • Analyze Q&A                   │
│  • Search news           • Generate report               │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL
- API keys for Tiingo and Massive.com

### Installation
```bash
# Clone repository
git clone https://github.com/PhilSing24/finreport.git
cd finreport

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
PG_DSN=postgresql:///finreport
TIINGO_API_KEY=your_tiingo_key
MASSIVE_API_KEY=your_massive_key
ANTHROPIC_API_KEY=your_claude_key
EOF

# Initialize database
psql -c "CREATE DATABASE finreport"
psql finreport -f migrations/001_create_earnings_tables.sql
psql finreport -f migrations/003_standardize_timestamps.sql
```

### Create Database Tables
```bash
# Run migrations in order
psql postgresql:///finreport -f migrations/001_create_earnings_tables.sql
psql postgresql:///finreport -f migrations/003_standardize_timestamps.sql
```

## 📊 Usage

### 1. Ingest News Articles
```bash
# Ingest news for a specific date and ticker
python -m aifinreport.ingestion.tiingo 2025-08-27 NVDA

# Ingest multiple dates (around earnings)
for date in 2025-08-{20..27} 2025-08-{28..31} 2025-09-{01..03}; do
    python -m aifinreport.ingestion.tiingo $date NVDA
done
```

### 2. Ingest Earnings Call Transcript

Prepare your transcript in this format:
```
---INTERVENTION---
SPEAKER: Jensen Huang
ROLE: CEO
TIME: 0:25:12
TEXT:
Thanks for the question...

---Q&A---
ANALYST: John Smith
COMPANY: Morgan Stanley
TIME: 0:35:45
QUESTION:
Can you provide color on...

RESPONDER: Jensen Huang
ROLE: CEO
TIME: 0:36:10
ANSWER:
Absolutely. Let me address that...

---INTERVENTION---
SPEAKER: Toshiya Hari
ROLE: VP - IR & Strategic Finance
TIME: 1:04:00
TEXT:
In closing, please note...
```

Then ingest (times are in UTC!):
```bash
python -m aifinreport.cli.ingest_earnings \
  data/earnings_transcripts/NVDA/NVDA_Q3_FY2026_2025-11-19.txt \
  NVDA Q3 2026 2025-11-19 22:00
```

**Note:** Call start time must be in UTC. The parser will automatically:
- Capture all interventions including closing remarks
- Parse Q&A sections with question-answer linking
- Generate accurate timestamps based on relative times

### 3. Fetch Stock Prices
```python
from datetime import datetime
from aifinreport.tools.market_data_tools import (
    fetch_ohlc_bars,
    fetch_earnings_price_analysis
)

# Single window fetch (times in UTC, automatically handled)
bars = fetch_ohlc_bars(
    ticker="NVDA",
    start_time=datetime(2025, 11, 19, 21, 30, 0),  # Will be treated as UTC
    end_time=datetime(2025, 11, 19, 23, 4, 0),
    interval="5min"
)

# 3-phase earnings analysis
analysis = fetch_earnings_price_analysis(
    ticker="NVDA",
    press_release_time=datetime(2025, 11, 19, 21, 30, 0),
    call_end_time=datetime(2025, 11, 19, 23, 4, 0)
)
# Returns:
# {
#   'pre_event': [14 daily bars before PR],
#   'event': [5-min bars during PR/call],
#   'post_event': [7 daily bars after call],
#   'summary': {metadata}
# }
```

### 4. Run AI Agent Analysis
```bash
# Analyze an earnings call
python -m aifinreport.agents.earnings_analyst

# Or programmatically:
from aifinreport.agents.earnings_analyst import run_agent
state = run_agent("earnings:nvda:q3-fy2026")
print(state['report'])
```

### 5. Query Database Directly
```python
from aifinreport.tools.database_tools import (
    get_earnings_call,
    get_prepared_remarks,
    get_qa_section,
    search_news_around_call
)

# Get call info
call = get_earnings_call("earnings:nvda:q3-fy2026")
# Returns: {
#   'id': 'earnings:nvda:q3-fy2026',
#   'ticker': 'NVDA',
#   'call_start_utc': datetime(...),  # timezone-aware
#   'call_date': date(...),
#   ...
# }

# Get Q&A exchanges
qa = get_qa_section("earnings:nvda:q3-fy2026")

# Get news around call
news = search_news_around_call("earnings:nvda:q3-fy2026", "pre-call")
```

## 📁 Project Structure
```
finreport/
├── src/aifinreport/
│   ├── agents/
│   │   └── earnings_analyst.py    # AI agent implementation
│   ├── cli/
│   │   ├── generate_report.py     # News report generation
│   │   └── ingest_earnings.py     # Earnings ingestion CLI
│   ├── ingestion/
│   │   ├── tiingo.py              # News ingestion
│   │   ├── earnings_parser.py     # Transcript parsing (with closing)
│   │   └── earnings_storage.py    # Database storage
│   ├── tools/
│   │   ├── database_tools.py      # 8 query functions
│   │   └── market_data_tools.py   # 3-phase price analysis
│   ├── analysis/
│   │   ├── selection.py           # Article selection
│   │   └── summarization.py       # Summarization
│   ├── database/
│   │   └── connection.py          # DB connection
│   └── config.py                  # Configuration
├── data/
│   └── earnings_transcripts/
│       └── NVDA/                  # NVDA transcripts (Q1, Q2, Q3 FY2026)
├── migrations/
│   ├── 001_create_earnings_tables.sql  # Initial schema
│   └── 003_standardize_timestamps.sql  # UTC timestamps (timestamptz)
├── notebooks/                     # Jupyter notebooks for visualization
├── requirements.txt
└── README.md
```

## 🗄️ Database Schema

### earnings_calls
- Earnings call metadata (ticker, quarter, fiscal year)
- **Call date and time in UTC** (timestamptz)
- Press release time (if available)
- Full transcript storage
- Total interventions and unique speakers

### call_interventions
- Individual statements with **UTC timestamps** (timestamptz)
- Speaker attribution (name, role, type: analyst/management/operator)
- Relative time from call start
- Q&A segmentation (is_question, is_answer, question_id)
- Analyst firm tracking
- **Captures all interventions including closing remarks**

### news_raw
- News article content and metadata
- Ticker associations (array)
- Published timestamps (UTC, timestamptz)

## 🔧 Tools & APIs

### Database Query Tools
```python
get_earnings_call(call_id)           # Load call metadata
get_prepared_remarks(call_id)        # Get non-Q&A content
get_qa_section(call_id)              # Get Q&A exchanges
search_news_around_call(call_id, window)  # Time-windowed news
get_analyst_questions(call_id)       # Questions only
get_management_answers(call_id)      # Answers with filtering
get_speaker_interventions(call_id, speaker)  # Filter by speaker
get_question_answer_pairs(call_id)   # Linked Q&A
```

### Market Data Tools
```python
fetch_ohlc_bars(ticker, start, end, interval)
# Get stock prices for any time window
# - Supports: 1min, 5min, 15min, 30min, 1hour, 1day
# - Timezone-aware: treats naive datetimes as UTC
# - Handles DELAYED status for future dates

fetch_earnings_price_analysis(ticker, pr_time, call_end)
# 3-phase analysis around earnings:
# - Phase 1: 14 days before (daily bars)
# - Phase 2: PR to call end (5-min bars)
# - Phase 3: 7 days after (daily bars, adjusted for data availability)
```

## 🎯 Example: Agent Output
```markdown
# NVDA Q3 FY2026 Earnings Analysis

## Executive Summary
Revenue exceeded expectations, but stock declined due to concerns 
raised in Q&A about China export restrictions...

## Key Metrics (from 3-phase price analysis)
- Pre-event trend: -4.45% (14 days before)
- Event reaction: +0.56% (during call)
- Post-event trend: -4.10% (3 days after)

## Management Commentary
CEO emphasized five competitive advantages...

## Analyst Focus (Q&A)
Primary concerns:
1. China revenue impact
2. Supply chain constraints
3. Memory pricing pressure

## Market Reaction
- Immediate: +0.56% during call
- Follow-through: -4.10% over next 3 days
- Post-call news spike: 73 articles

## Investment Thesis
Despite strong fundamentals, geopolitical headwinds create 
near-term uncertainty...
```

## 🛣️ Roadmap

- [x] News ingestion pipeline
- [x] Earnings call ingestion with full transcript capture
- [x] Database schema with UTC timestamps (timestamptz)
- [x] Parser captures closing remarks
- [x] 3-phase price analysis around earnings
- [x] Timezone handling for Singapore (UTC+8)
- [x] Agent foundation with data gathering tools
- [ ] LLM-based metric extraction
- [ ] Sentiment analysis
- [ ] Complete agent workflow
- [ ] Multi-agent collaboration
- [ ] Automated report distribution
- [ ] Web dashboard
- [ ] Real-time WebSocket integration

## 🐛 Known Limitations

- **Morning session data**: Some intraday bars may be unavailable for the first 2.5 hours of trading (market open to noon EST) depending on data provider settlement times
- **Recent data**: Post-event analysis adjusted to avoid DELAYED status (ends 2 days before current date)
- **Timezone**: All times stored in UTC; ensure call start times are provided in UTC when ingesting

## 📝 License

This project is for educational and research purposes.

## 🤝 Contributing

This is a personal research project. Feel free to fork and adapt for your own use.

## ⚠️ Disclaimer

This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.

---

## 📊 Current Data

**NVIDIA Earnings Calls (FY2026):**
- Q1: May 29, 2025 (31 interventions)
- Q2: August 27, 2025 (48 interventions)
- Q3: November 19, 2025 (43 interventions)

All calls include complete transcripts with Q&A and closing remarks.