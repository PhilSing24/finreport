# AIFinReport - AI-Powered Financial Analysis System

An **agentic AI application** that uses autonomous AI agents to analyze financial data. The system independently processes earnings call transcripts, correlates news sentiment with semantic ranking, and tracks market movements to generate comprehensive investment insights.

## 🎯 Overview

AIFinReport automatically analyzes earnings by:

- **Pre-Event Analysis:** Ranks news articles semantically and extracts market expectations
- **Event Analysis:** Extracts actual results from earnings press releases
- **Gap Analysis:** Compares expectations vs actuals to identify surprises and predict market impact
- Processing detailed earnings call transcripts (prepared remarks + Q&A + closing)
- Fetching stock price data for any time period

## ✨ Features

### Complete Earnings Analysis Pipeline

**🔍 Pre-Event Expectations (7 days before earnings)**
- Semantic ranking of news articles using local embeddings
- Extract consensus estimates, guidance expectations, key themes
- Identify analyst sentiment and potential surprises
- **Cost:** ~$0.01 per analysis (1 LLM call)

**📄 Press Release Extraction (Day of earnings)**
- Extract actual financial results from earnings press releases
- Parse complex table formats automatically
- Capture guidance, management commentary, new announcements
- **Cost:** ~$0.01 per analysis (1 LLM call)

**⚡ Gap Analysis (Expectations vs Actuals)**
- Automatically compare predicted vs actual results
- Identify positive/negative surprises with significance scoring
- Generate bull/bear takes and market impact predictions
- Predict questions for Q&A session
- **Cost:** ~$0.04 per analysis (1 LLM call)

**Total Pipeline Cost:** ~$0.06 per complete earnings analysis

### Data Ingestion
- **News Articles**: Automated ingestion from Tiingo API with full body text
- **Press Releases**: Extract and store earnings announcements
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
- **Pre-Event Summarizer**: Analyzes news to extract market expectations
  - **Semantic article ranking** using local embeddings (sentence-transformers)
  - Ranks by relevance to earnings expectations
  - No API rate limits or costs for ranking
  - Universal prompts work for any company/quarter
  
- **Press Release Extractor**: Extracts actual results from press releases
  - Handles complex table formats (vertical lists, nested data)
  - Extracts GAAP/non-GAAP metrics, segment performance, guidance
  - Captures management commentary and new announcements
  
- **Gap Analyzer**: Compares expectations vs actuals
  - Automatic surprise detection (beats/misses)
  - Significance scoring (HIGH/MEDIUM/LOW)
  - Market impact assessment with confidence levels
  - Generates investment insights (bull/bear cases, Q&A predictions)

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
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                DATA SOURCES                                      │
├──────────────────────┬─────────────────────────┬────────────────────────────────┤
│   Tiingo News API    │   Manual Entry (PDFs)   │   Massive.com API              │
│   • News articles    │   • Call transcripts    │   • Stock prices               │
│   • Published times  │   • Press releases      │   • OHLC data                  │
└──────────┬───────────┴────────────┬────────────┴──────────┬─────────────────────┘
           │                        │                        │
           ▼                        ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INGESTION LAYER                                     │
├──────────────────────┬─────────────────────────┬────────────────────────────────┤
│  tiingo.py           │  ingest_earnings.py     │  market_data_tools             │
│  └─> news_raw        │  └─> earnings_parser    │  └─> (on-demand)               │
│                      │  └─> earnings_storage   │                                │
│  ingest_press_       │  └─> earnings_calls     │                                │
│  release.py          │  └─> call_interventions │                                │
│  └─> news_raw        │                         │                                │
└──────────────────────┴─────────────────────────┴────────────────────────────────┘
           │                        │                        │
           └────────────────────────┴────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL DATABASE (UTC)                                   │
├────────────────────────────────┬────────────────────────────────────────────────┤
│   earnings_calls               │   call_interventions    │   news_raw           │
│   ├─ press_release_time_utc ⏰ │   ├─ timestamp_utc ⏰   │   ├─ full_body       │
│   ├─ call_end_utc ⏰           │   ├─ is_question        │   ├─ is_press_release│
│   └─ full_transcript           │   └─ question_id        │   └─ related_call_id │
└────────────────────────────────┴─────────────────────────┴──────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TOOLS LAYER                                         │
├──────────────────────┬──────────────────────────┬───────────────────────────────┤
│  database_tools.py   │  market_data_tools.py    │  news_ranker.py               │
│  ├─ search_news()    │  ├─ fetch_ohlc_bars()    │  ├─ Local embeddings          │
│  ├─ get_press_       │  └─ Massive.com API      │  │   (all-MiniLM-L6-v2)        │
│  │   release()       │                          │  └─ Semantic ranking          │
│  └─ get_qa_section() │                          │                               │
└──────────────────────┴──────────────────────────┴───────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            AGENT LAYER                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  📊 STEP 1: Pre-Event Expectations                                               │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  news_period_analyst.py + pre_event_summarizer.py                      │    │
│  │  • Fetch news (7 days before earnings)                                 │    │
│  │  • Rank by semantic relevance (local embeddings)                       │    │
│  │  • LLM summarizes top 10 articles                                      │    │
│  │  • Extract: consensus estimates, guidance expectations, themes         │    │
│  │  → Output: expectations.json                                           │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                              │
│  📄 STEP 2: Press Release Extraction                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  press_release_extractor.py                                             │    │
│  │  • Retrieve press release from database                                │    │
│  │  • LLM extracts actual results (handles messy tables)                  │    │
│  │  • Extract: revenue, EPS, margins, segments, guidance                  │    │
│  │  → Output: actuals.json                                                │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                  ↓                                              │
│  ⚡ STEP 3: Gap Analysis                                                         │
│  ┌────────────────────────────────────────────────────────────────────────┐    │
│  │  gap_analyzer.py                                                        │    │
│  │  • Compare expectations vs actuals                                     │    │
│  │  • Identify surprises (beats/misses)                                   │    │
│  │  • Score significance (HIGH/MEDIUM/LOW)                                │    │
│  │  • Generate investment insights                                        │    │
│  │  → Output: gap_analysis.json                                           │    │
│  └────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           INVESTMENT INSIGHTS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Positive/Negative Surprises with $ amounts and %                             │
│  • Significance Scoring (HIGH/MEDIUM/LOW)                                       │
│  • Market Impact Assessment (+5-7%, HIGH confidence)                            │
│  • Bull/Bear Takes                                                              │
│  • Expected Q&A Questions                                                       │
│  • New Information Not Anticipated                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL
- API keys for Tiingo, Massive.com, and Mistral

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
LLM_PROVIDER=mistral
LLM_MODEL=mistral-small-latest
EOF

# Initialize database
psql -c "CREATE DATABASE finreport"
psql finreport -f migrations/001_create_earnings_tables.sql
psql finreport -f migrations/002_add_press_release_columns.sql
psql finreport -f migrations/003_standardize_timestamps.sql
psql finreport -f migrations/004_add_event_timestamps.sql
```

## 📊 Usage

### Complete Earnings Analysis Pipeline

#### **Step 1: Ingest Data**
```bash
# 1. Ingest news articles (7 days before earnings)
for date in 2025-11-{12..19}; do
    python -m aifinreport.ingestion.tiingo $date NVDA
    sleep 1
done

# 2. Ingest press release
python -m aifinreport.cli.ingest_press_release \
  data/press_releases/NVDA/NVDA_Q3_FY2026_PR.pdf \
  earnings:nvda:q3-fy2026

# 3. Ingest earnings call transcript
python -m aifinreport.cli.ingest_earnings \
  data/earnings_transcripts/NVDA/NVDA_Q3_FY2026_2025-11-19.txt \
  NVDA Q3 2026 2025-11-19 22:00
```

#### **Step 2: Run Analysis Pipeline**
```bash
# Option A: Run each step separately

# Step 1: Pre-event expectations
python -m aifinreport.agents.pre_event_summarizer

# Step 2: Extract actuals from press release
python -m aifinreport.agents.press_release_extractor earnings:nvda:q3-fy2026

# Step 3: Gap analysis
python -m aifinreport.agents.gap_analyzer earnings:nvda:q3-fy2026
```

**Or use programmatically:**
```python
from datetime import datetime, timezone, timedelta
from aifinreport.agents.news_period_analyst import analyze_news_period
from aifinreport.agents.pre_event_summarizer import summarize_pre_event_expectations
from aifinreport.agents.press_release_extractor import extract_press_release_facts
from aifinreport.agents.gap_analyzer import compare_expectations_vs_actuals

# Step 1: Pre-Event Analysis
pr_time = datetime(2025, 11, 19, 21, 30, 0, tzinfo=timezone.utc)

result = analyze_news_period(
    ticker="NVDA",
    start_date=pr_time - timedelta(days=7),
    end_date=pr_time,
    quarter="Q3",
    top_n_articles=10,
    context="Pre-earnings expectations"
)

expectations = summarize_pre_event_expectations(
    ranked_articles=result['ranked_news'],
    company_name="NVIDIA Corporation",
    quarter="Q3 FY2026",
    ticker="NVDA"
)

# Step 2: Extract Actuals
actuals = extract_press_release_facts(
    call_id="earnings:nvda:q3-fy2026",
    company_name="NVIDIA Corporation",
    quarter="Q3 FY2026"
)

# Step 3: Gap Analysis
gap_analysis = compare_expectations_vs_actuals(
    expectations=expectations,
    actuals=actuals,
    company_name="NVIDIA Corporation",
    quarter="Q3 FY2026"
)

# View results
print(gap_analysis['positive_surprises'])
print(gap_analysis['market_impact_assessment'])
```

#### **Example Output**
```
⚡ GAP ANALYSIS: EXPECTATIONS VS ACTUALS

✅ POSITIVE SURPRISES (Beats)

🔥 REVENUE - MEDIUM significance
   Expected: $54.59B (HIGH confidence) 🟢
   Actual:   $57.0B
   Beat by:  $2.41B (+4.4%)

📈 EPS - MEDIUM significance
   Expected: $1.24 (HIGH confidence) 🟢
   Actual:   $1.30
   Beat by:  $0.06 (+4.8%)

📈 DATA CENTER - MEDIUM significance
   Expected: $48.94B (MEDIUM confidence) 🟡
   Actual:   $51.2B
   Beat by:  $2.26B (+4.6%)

📊 MARKET IMPACT ASSESSMENT

🚀 Overall Verdict: STRONG BEAT

💹 Expected Stock Reaction: +5-7%
   Confidence: HIGH

🔑 Key Reaction Drivers:
   • Strong revenue and EPS beats
   • Data Center exceeding expectations
   • Q4 guidance above consensus
   • Blackwell momentum "off the charts"
   • OpenAI 10GW partnership

📈 Bull Take:
   AI infrastructure super-cycle accelerating, 
   Blackwell demand exceeding supply

📉 Bear Take:
   Valuation concerns, tough comps ahead
```

### Other Usage Examples

**Fetch Stock Prices:**
```python
from aifinreport.tools.market_data_tools import fetch_ohlc_bars

bars = fetch_ohlc_bars(
    ticker="NVDA",
    start_time=datetime(2025, 11, 12),
    end_time=datetime(2025, 11, 19),
    interval="1day"
)
```

**Query Database:**
```python
from aifinreport.tools.database_tools import (
    get_earnings_call,
    search_news,
    get_press_release
)

call = get_earnings_call("earnings:nvda:q3-fy2026")
pr = get_press_release("earnings:nvda:q3-fy2026")
news = search_news("NVDA", start_time=..., end_time=...)
```

## 📁 Project Structure
```
finreport/
├── src/aifinreport/
│   ├── agents/
│   │   ├── news_period_analyst.py      # Analyze any time period
│   │   ├── news_ranker.py              # Semantic article ranking
│   │   ├── pre_event_summarizer.py     # Extract expectations ← NEW
│   │   ├── press_release_extractor.py  # Extract actuals ← NEW
│   │   ├── gap_analyzer.py             # Compare & analyze ← NEW
│   │   └── earnings_analyst.py         # Full workflow (legacy)
│   ├── cli/
│   │   ├── generate_report.py          # Report generation
│   │   ├── ingest_earnings.py          # Earnings ingestion CLI
│   │   └── ingest_press_release.py     # Press release ingestion
│   ├── ingestion/
│   │   ├── tiingo.py                   # News ingestion
│   │   ├── earnings_parser.py          # Transcript parsing
│   │   └── earnings_storage.py         # Database storage
│   ├── tools/
│   │   ├── database_tools.py           # Database queries
│   │   └── market_data_tools.py        # Price analysis
│   └── config.py                       # Configuration
├── data/
│   ├── earnings_transcripts/NVDA/      # NVDA transcripts (Q1, Q2, Q3)
│   ├── press_releases/NVDA/            # Press release PDFs
│   ├── expectations_nvda_q3-fy2026.json  # Example output
│   ├── actuals_nvda_q3-fy2026.json       # Example output
│   └── gap_analysis_nvda_q3-fy2026.json  # Example output
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

## 🔧 Key Technologies

### Semantic Article Ranking
- **Model:** all-MiniLM-L6-v2 (sentence-transformers)
- **Purpose:** Rank news articles by relevance to earnings expectations
- **Advantages:**
  - Free (runs locally)
  - Fast (process 62 articles in ~2 seconds)
  - No API rate limits
  - 80MB model size

### LLM-Based Extraction
- **Model:** Mistral Small (configurable via .env)
- **Purpose:** Extract structured data from unstructured text
- **Advantages:**
  - Handles messy table formats automatically
  - Universal prompts (works for any company/quarter)
  - Intelligent matching and comparison
  - Understands context (GAAP vs non-GAAP, Q/Q vs Y/Y)

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

## 💰 Cost Analysis

**Per Complete Earnings Analysis:**
- Pre-event summarization: ~$0.01 (1 LLM call, 5K tokens)
- Press release extraction: ~$0.01 (1 LLM call, 7K tokens)
- Gap analysis: ~$0.04 (1 LLM call, 10K tokens)
- **Total: ~$0.06 per earnings event**

**For 100 earnings analyses per quarter: $6**

## 🛣️ Roadmap

- [x] News ingestion pipeline
- [x] Press release ingestion and storage
- [x] Earnings call ingestion with full transcript
- [x] Database schema with UTC timestamps
- [x] Press release timestamp tracking
- [x] Semantic article ranking (local embeddings)
- [x] News period analysis (flexible date ranges)
- [x] **Pre-event expectations summarization**
- [x] **Press release facts extraction**
- [x] **Gap analysis with surprise detection**
- [x] **Market impact assessment**
- [ ] Post-earnings analysis workflow (5 days after call)
- [ ] Q&A theme extraction from call transcripts
- [ ] Multi-quarter trend analysis
- [ ] Automated PDF/HTML report generation
- [ ] Real-time stock movement tracking
- [ ] Web dashboard
- [ ] Multi-agent collaboration

## 📝 Special Installation Notes

### Sentence Transformers
Due to pip dependency resolution issues, install separately:
```bash
pip install --upgrade pip
pip install sentence-transformers --no-deps
pip install torch transformers huggingface-hub tokenizers safetensors
```

### Environment Variables
Create a `.env` file with:
```bash
PG_DSN=postgresql:///finreport
TIINGO_API_KEY=your_key
MASSIVE_API_KEY=your_key
MISTRAL_API_KEY=your_key
LLM_PROVIDER=mistral
LLM_MODEL=mistral-small-latest
```

## 🐛 Known Limitations

- **Semantic ranking:** First run downloads ~90MB model (one-time)
- **Recent data:** Some intraday bars may have delays
- **Timezone:** All times must be provided in UTC
- **LLM costs:** Using mistral-small-latest to minimize costs; mistral-large-latest provides better quality but costs 3-4x more

## 📝 License

This project is for educational and research purposes.

## 🤝 Contributing

This is a personal research project. Feel free to fork and adapt for your own use.

## ⚠️ Disclaimer

This tool is for informational purposes only. Not financial advice. Always do your own research before making investment decisions.

---

## 📊 Example Analysis Results

**NVIDIA Q3 FY2026 Earnings (November 19, 2025):**

**Pre-Event Expectations (from 10 analyst articles):**
- Revenue: $54.59B expected
- EPS: $1.24 expected
- Data Center: $48.94B expected
- Market Sentiment: Cautiously optimistic

**Actual Results (from press release):**
- Revenue: $57.0B (+22% Q/Q, +62% Y/Y)
- EPS: $1.30 (GAAP and non-GAAP)
- Data Center: $51.2B (+25% Q/Q, +66% Y/Y)
- Q4 Guidance: $65.0B ± 2%

**Gap Analysis:**
- ✅ Revenue beat: +$2.41B (+4.4%)
- ✅ EPS beat: +$0.06 (+4.8%)
- ✅ Data Center beat: +$2.26B (+4.6%)
- ✅ Q4 guidance above consensus
- 🔥 Blackwell "off the charts"
- 🤝 OpenAI 10GW partnership announced
- **Verdict:** STRONG BEAT
- **Predicted reaction:** +5-7% (HIGH confidence)

All analysis completed in ~30 seconds for ~$0.06.