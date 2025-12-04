# AIFinReport - AI-Powered Financial Analysis System

An **agentic AI application** that uses autonomous AI agents to analyze financial data. The system independently processes earnings call transcripts, correlates news sentiment with semantic ranking, and tracks market movements to generate comprehensive investment insights.

## 🎯 Overview

AIFinReport automatically analyzes earnings calls by:

- Processing detailed earnings call transcripts (prepared remarks + Q&A + closing)
- **Semantic ranking of news articles** using local embeddings (no API limits)
- Fetching stock price data for any time period
- Generating actionable investment briefs using AI agents

## ✨ Features

### Data Ingestion
- **News Articles**: Automated ingestion from Tiingo API
- **Press Releases**: Store earnings press releases (PDFs) in database
- **Earnings Calls**: Parse structured transcripts with:
  - Speaker attribution and roles
  - Precise UTC timestamps
  - Q&A segmentation (questions, answers, analyst firms)
  - Closing remarks
- **Stock Prices**: Real-time and historical OHLC data from Massive.com API
  - Flexible time windows (any date range)
  - Multiple intervals (1min, 5min, 15min, 1hour, 1day)
  - Timezone-aware (UTC) with Singapore (UTC+8) support

### AI Agent Analysis
- **News Period Analyst**: Analyze news and stock performance for any time period
  - **Semantic article ranking** using local embeddings (sentence-transformers)
  - Rank by relevance to earnings expectations
  - Works for pre-earnings, post-earnings, or custom periods
  - No API rate limits or costs
- **Earnings Impact Analyst**: Full earnings call analysis workflow
  - Extracts key financial metrics from management remarks
  - Identifies analyst concerns from Q&A sessions
  - Correlates market reaction with call content
  - Synthesizes news sentiment around earnings events

### Database
PostgreSQL with structured storage for:
- Earnings call metadata with **press release timestamps**
- Timestamped interventions (speaker, role, content)
- Q&A segmentation with question-answer linking
- News articles with ticker associations and **full body text**
- **Press releases** marked and linked to earnings calls
- Time-series ready for price correlation
- **All timestamps in UTC** (timestamptz)

## 🏗️ Architecture
```
┌─────────────────────────────────────────────────────────┐
│                    Data Sources                          │
├─────────────┬──────────────────┬────────────────────────┤
│  Tiingo API │  Manual Entry    │    Massive.com API     │
│   (News)    │  (Transcripts    │   (Stock Prices)       │
│             │   & Press PDFs)  │                        │
└──────┬──────┴────────┬─────────┴──────────┬─────────────┘
       │               │                    │
       ▼               ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│              Ingestion Layer                             │
│  • tiingo.py               • earnings_parser.py          │
│  • ingest_press_release.py • earnings_storage.py         │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                PostgreSQL Database                       │
│  • earnings_calls (with press_release_time_utc)          │
│  • call_interventions (full capture)                     │
│  • news_raw (with full_body + press releases)            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Agent Tools                            │
│  • database_tools.py (search_news, get_press_release)    │
│  • market_data_tools.py (price analysis)                 │
│  • news_ranker.py (semantic article ranking)             │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│               News Period Analyst Agent                  │
│  • Analyze any time period  • Semantic article ranking   │
│  • Stock performance         • Local embeddings          │
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

# Note: sentence-transformers may need special installation
pip install --upgrade pip
pip install sentence-transformers --no-deps
pip install torch transformers huggingface-hub tokenizers safetensors

# Create .env file
cat > .env << EOF
PG_DSN=postgresql:///finreport
TIINGO_API_KEY=your_tiingo_key
MASSIVE_API_KEY=your_massive_key
MISTRAL_API_KEY=your_mistral_key
EOF

# Initialize database
psql -c "CREATE DATABASE finreport"
psql finreport -f migrations/001_create_earnings_tables.sql
psql finreport -f migrations/002_add_press_release_columns.sql
psql finreport -f migrations/003_standardize_timestamps.sql
psql finreport -f migrations/004_add_event_timestamps.sql
```

## 📊 Usage

### 1. Ingest News Articles
```bash
# Ingest news for a specific date and ticker
python -m aifinreport.ingestion.tiingo 2025-11-19 NVDA

# Ingest multiple dates (around earnings)
for date in 2025-11-{05..25}; do
    python -m aifinreport.ingestion.tiingo $date NVDA
    sleep 1
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

### 3. Ingest Press Release (Optional)

Store press releases for reference:
```bash
# Ingest a press release PDF
python -m aifinreport.cli.ingest_press_release \
  data/press_releases/NVDA/NVDA_Q3_FY2026_PR_2025-11-19.pdf \
  earnings:nvda:q3-fy2026
```

This stores:
- Press release text in `news_raw` table
- Marked as `is_press_release = TRUE`
- Linked to earnings call via `related_call_id`
- Enables retrieval with `get_press_release(call_id)`

### 4. Analyze News Period with Semantic Ranking
```python
from datetime import datetime, timezone, timedelta
from aifinreport.agents.news_period_analyst import analyze_news_period

# Pre-earnings analysis (7 days before press release)
pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=timezone.utc)

result = analyze_news_period(
    ticker="NVDA",
    start_date=pr_time - timedelta(days=7),
    end_date=pr_time,
    quarter="Q3",
    top_n_articles=10,
    context="Pre-earnings expectations"
)

# Output:
# - Finds all news articles in date range
# - Ranks by semantic similarity to earnings expectations
# - Returns top 10 most relevant articles
# - Calculates stock performance for the period
```

**Or run from command line:**
```bash
python -m aifinreport.agents.news_period_analyst
```

**Example output:**
```
📊 NEWS PERIOD ANALYSIS
======================================================================

Ticker: NVDA
Quarter: Q3
Context: Pre-earnings expectations (7 days before press release)

Period: 2025-11-12 → 2025-11-19
Duration: 7 days

📰 Fetching news articles...
   Found 62 total articles

🔍 Ranking articles by relevance using local embeddings...
   Loading embedding model (one-time, ~2 seconds)...
   ✅ Model loaded
   Ranking 62 articles using local embeddings...
   ✅ Ranked by semantic relevance
   Selected top 10 most relevant articles

======================================================================
Top 10 Most Relevant Articles (by semantic similarity)
======================================================================

1. [Score: 0.747] Insights Into Nvidia (NVDA) Q3: Wall Street Projections
   Published: 2025-11-14 22:15
   ...

💹 Stock Performance:
   NVDA: -3.76%
   Start: $193.80 (2025-11-12)
   End:   $186.52 (2025-11-19)
```

### 5. Fetch Stock Prices
```python
from datetime import datetime
from aifinreport.tools.market_data_tools import fetch_ohlc_bars

# Get prices for any time window
bars = fetch_ohlc_bars(
    ticker="NVDA",
    start_time=datetime(2025, 11, 12),
    end_time=datetime(2025, 11, 19),
    interval="1day"
)
```

### 6. Query Database
```python
from aifinreport.tools.database_tools import (
    get_earnings_call,
    search_news,
    get_qa_section,
    get_press_release
)

# Get call info (includes press_release_time_utc)
call = get_earnings_call("earnings:nvda:q3-fy2026")

# Get press release
pr = get_press_release("earnings:nvda:q3-fy2026")

# Search news for specific date range
news = search_news(
    ticker="NVDA",
    start_time=datetime(2025, 11, 12),
    end_time=datetime(2025, 11, 19)
)

# Get Q&A exchanges
qa = get_qa_section("earnings:nvda:q3-fy2026")
```

## 📁 Project Structure
```
finreport/
├── src/aifinreport/
│   ├── agents/
│   │   ├── news_period_analyst.py  # Analyze any time period
│   │   ├── news_ranker.py          # Semantic article ranking
│   │   └── earnings_analyst.py     # Full earnings workflow
│   ├── cli/
│   │   ├── generate_report.py      # Report generation
│   │   ├── ingest_earnings.py      # Earnings ingestion CLI
│   │   └── ingest_press_release.py # Press release ingestion
│   ├── ingestion/
│   │   ├── tiingo.py               # News ingestion
│   │   ├── earnings_parser.py      # Transcript parsing
│   │   └── earnings_storage.py     # Database storage
│   ├── tools/
│   │   ├── database_tools.py       # Database queries
│   │   └── market_data_tools.py    # Price analysis
│   └── config.py                   # Configuration
├── data/
│   ├── earnings_transcripts/
│   │   └── NVDA/                   # NVDA call transcripts (Q1, Q2, Q3)
│   └── press_releases/
│       └── NVDA/                   # Press release PDFs
├── migrations/
│   ├── 001_create_earnings_tables.sql
│   ├── 002_add_press_release_columns.sql
│   ├── 003_standardize_timestamps.sql
│   └── 004_add_event_timestamps.sql
├── requirements.txt
└── README.md
```

## 🗄️ Database Schema

### earnings_calls
- Earnings call metadata (ticker, quarter, fiscal year)
- **Call start time in UTC** (timestamptz)
- **Press release time in UTC** (timestamptz)
- **Call end time in UTC** (timestamptz)
- Full transcript storage

### call_interventions
- Individual statements with **UTC timestamps** (timestamptz)
- Speaker attribution (name, role, type)
- Q&A segmentation
- **Captures all interventions including closing remarks**

### news_raw
- News article content and metadata
- **Full body text** for semantic analysis
- Ticker associations (array)
- Published timestamps (UTC, timestamptz)
- **Press release flags:**
  - `is_press_release`: Boolean flag
  - `press_release_type`: Type (earnings, guidance, etc.)
  - `related_call_id`: Links to earnings call

## 🔧 Key Tools

### News Period Analyst
- **Purpose:** Analyze news and stock performance for any time period
- **Semantic Ranking:** Uses local embeddings (all-MiniLM-L6-v2)
- **No API Limits:** Runs locally, process unlimited articles
- **Use Cases:**
  - Pre-earnings: 7 days before press release
  - Post-earnings: 5 days after call
  - Custom: Any date range

### Database Query Tools
```python
search_news(ticker, start_time, end_time)    # Flexible date search
get_earnings_call(call_id)                   # Load call metadata
get_press_release(call_id)                   # Get official press release
get_prepared_remarks(call_id)                # Get non-Q&A content
get_qa_section(call_id)                      # Get Q&A exchanges
```

### Market Data Tools
```python
fetch_ohlc_bars(ticker, start, end, interval)
# Get stock prices for any time window
# Supports: 1min, 5min, 15min, 30min, 1hour, 1day
```

## 🎯 Example: News Period Analysis
```python
# Analyze 7 days before earnings
from datetime import datetime, timezone, timedelta
from aifinreport.agents.news_period_analyst import analyze_news_period

pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=timezone.utc)

result = analyze_news_period(
    ticker="NVDA",
    start_date=pr_time - timedelta(days=7),
    end_date=pr_time,
    quarter="Q3",
    top_n_articles=10,
    context="Pre-earnings expectations"
)

# Results include:
# - Top 10 most relevant articles (ranked semantically)
# - Stock performance: -3.76%
# - 62 articles analyzed, 10 selected
```

## 🛣️ Roadmap

- [x] News ingestion pipeline
- [x] Press release ingestion and storage
- [x] Earnings call ingestion with full transcript
- [x] Database schema with UTC timestamps
- [x] Press release timestamp tracking
- [x] Semantic article ranking (local embeddings)
- [x] News period analysis (flexible date ranges)
- [ ] LLM summarization of top articles
- [ ] Post-earnings analysis workflow
- [ ] Complete earnings report generation
- [ ] Multi-agent collaboration
- [ ] Web dashboard
- [ ] Real-time WebSocket integration

## 📝 Special Installation Notes

### Sentence Transformers
Due to pip dependency resolution issues, install separately:
```bash
pip install --upgrade pip
pip install sentence-transformers --no-deps
pip install torch transformers huggingface-hub tokenizers safetensors
```

## 🐛 Known Limitations

- **Semantic ranking:** First run downloads ~90MB model (one-time)
- **Recent data:** Some intraday bars may have delays
- **Timezone:** All times must be provided in UTC

## 📝 License

This project is for educational and research purposes.

## ⚠️ Disclaimer

This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.

---

## 📊 Current Data

**NVIDIA Earnings Calls (FY2026):**
- Q1: May 28, 2025 @ 20:30 UTC (PR) / 21:00 UTC (Call)
- Q2: August 27, 2025 @ 20:30 UTC (PR) / 21:00 UTC (Call)
- Q3: November 19, 2025 @ 21:30 UTC (PR) / 22:00 UTC (Call)

All calls include:
- Complete transcripts with Q&A and closing remarks
- Press release times for accurate pre-event analysis
- Press release PDFs stored in database