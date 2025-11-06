# AIFinReport - AI-Powered Financial Analysis System

An intelligent financial analysis platform that combines earnings call transcripts, news articles, and market data to generate comprehensive investment insights using AI agents.

## 🎯 Overview

AIFinReport automatically analyzes earnings calls by:
- Processing detailed earnings call transcripts (prepared remarks + Q&A)
- Correlating with news sentiment before and after calls
- Analyzing stock price movements during calls
- Generating actionable investment briefs using AI agents

## ✨ Features

### Data Ingestion
- **News Articles**: Automated ingestion from Tiingo API
- **Earnings Calls**: Parse structured transcripts with speaker attribution, timestamps, and Q&A segmentation
- **Stock Prices**: Real-time and historical OHLC data from Massive.com API

### AI Agent Analysis
- **Earnings Impact Analyst**: Autonomous agent that analyzes earnings calls and generates investment briefs
- Extracts key financial metrics from management remarks
- Identifies analyst concerns from Q&A sessions
- Correlates market reaction with call content
- Synthesizes news sentiment around earnings events

### Database
- PostgreSQL with structured storage for:
  - Earnings call metadata and full transcripts
  - Timestamped interventions (speaker, role, content)
  - Q&A segmentation (questions, answers, analyst firms)
  - News articles with ticker associations
  - Time-series ready for price correlation

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
├─────────────┬──────────────────┬────────────────────────┤
│  Tiingo API │  Yahoo Finance   │    Massive.com API     │
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
│  • news_raw              • call_interventions            │
│  • earnings_calls        • news_normalized               │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent Tools                            │
│  • database_tools.py (8 query functions)                 │
│  • market_data_tools.py (price fetching)                 │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│            Earnings Impact Analyst Agent                 │
│  • Load call metadata    • Fetch stock prices            │
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
psql finreport -f migrations/create_earnings_tables.sql
```

### Create Database Tables
```bash
# Run migration to create tables
psql postgresql:///finreport -f migrations/create_earnings_tables.sql
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
```

Then ingest:
```bash
python -m aifinreport.cli.ingest_earnings \
  data/earnings_transcripts/NVDA/NVDA_Q2_FY2026_2025-08-27.txt \
  NVDA Q2 2026 2025-08-27 21:00
```

### 3. Run AI Agent Analysis
```bash
# Analyze an earnings call
python -m aifinreport.agents.earnings_analyst

# Or programmatically:
from aifinreport.agents.earnings_analyst import run_agent
state = run_agent("earnings:nvda:q2-fy2026")
print(state['report'])
```

### 4. Query Database Directly
```python
from aifinreport.tools.database_tools import (
    get_earnings_call,
    get_prepared_remarks,
    get_qa_section,
    search_news_around_call
)

# Get call info
call = get_earnings_call("earnings:nvda:q2-fy2026")

# Get Q&A exchanges
qa = get_qa_section("earnings:nvda:q2-fy2026")

# Get news around call
news = search_news_around_call("earnings:nvda:q2-fy2026", "pre-call")
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
│   │   ├── earnings_parser.py     # Transcript parsing
│   │   └── earnings_storage.py    # Database storage
│   ├── tools/
│   │   ├── database_tools.py      # 8 query functions
│   │   └── market_data_tools.py   # Stock price fetching
│   ├── analysis/
│   │   ├── selection.py           # Article selection
│   │   └── summarization.py       # Summarization
│   ├── database/
│   │   └── connection.py          # DB connection
│   └── config.py                  # Configuration
├── data/
│   └── earnings_transcripts/      # Transcript files
├── migrations/
│   └── create_earnings_tables.sql # Database schema
├── notebooks/                     # Jupyter notebooks
├── requirements.txt
└── README.md
```

## 🗄️ Database Schema

### `earnings_calls`
- Earnings call metadata (ticker, quarter, date, time)
- Full transcript storage
- Total interventions and speakers

### `call_interventions`
- Individual statements with UTC timestamps
- Speaker attribution (name, role, type)
- Q&A segmentation (is_question, is_answer, question_id)
- Analyst firm tracking

### `news_raw`
- News article content and metadata
- Ticker associations (array)
- Published timestamps (UTC)

## 🔧 Tools & APIs

### Database Query Tools
1. `get_earnings_call()` - Load call metadata
2. `get_prepared_remarks()` - Get non-Q&A content
3. `get_qa_section()` - Get Q&A exchanges
4. `search_news_around_call()` - Time-windowed news search
5. `get_analyst_questions()` - Questions only
6. `get_management_answers()` - Answers with filtering
7. `get_speaker_interventions()` - Filter by speaker
8. `get_question_answer_pairs()` - Linked Q&A

### Market Data Tools
- `fetch_ohlc_bars()` - Get stock prices for any time window

## 🎯 Example: Agent Output
```markdown
# NVDA Q2 FY2026 Earnings Analysis

## Executive Summary
Revenue beat expectations at $46.7B (+69% YoY), but stock declined 
-0.5% due to China concerns raised in Q&A...

## Key Metrics
- Revenue: $46.7B (vs consensus $45.2B)
- Data Center: $39B (+73% YoY)
- Guidance: Q3 $45B

## Management Commentary
CFO emphasized Blackwell ramp success...

## Analyst Focus (Q&A)
5 questions, primary concerns:
1. China revenue impact ($8B loss)
2. Export controls

## Market Reaction
Price: $182.91 → $182.03 (-0.5%)
Post-call news spike: 73 articles (vs 67 pre-call)

## Investment Thesis
Despite strong results, China headwinds create near-term uncertainty...
```

## 🛣️ Roadmap

- [x] News ingestion pipeline
- [x] Earnings call ingestion
- [x] Database schema for time-series
- [x] Agent foundation with data gathering
- [ ] LLM-based metric extraction
- [ ] Sentiment analysis
- [ ] Multi-agent collaboration
- [ ] Automated report distribution
- [ ] Web dashboard
- [ ] Real-time WebSocket integration

## 📝 License

This project is for educational and research purposes.

## 🤝 Contributing

This is a personal research project. Feel free to fork and adapt for your own use.

## ⚠️ Disclaimer

This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.