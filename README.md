🧠 FinReport: AI-Powered Financial News Summrizer

FinReport is an ongoing Python project that generates structured, investor-style summaries for selected tickers and time periods using LLMs (Mistral or OpenAI GPT).
It ingests Finance Yahoo articles, enriches them with full-text, keywords, and heuristics, ranks relevance, and produces concise Markdown summaries.
Planned: integrate kdb+ time-series (prices, volumes, fundamentals) to contextualize news with market metrics, and add an AI agent that tracks tone shifts across weekly summaries to proactively alert investors.

🚀 Project Overview

FinReport automates the process of analyzing recent financial news to generate institutional-grade insights.
It follows a modular pipeline:

Ingestion – Raw news data stored in a PostgreSQL table (news_raw), with metadata such as title, tickers, keywords, and full_body.

Selection – Intelligent scoring function filters the most relevant articles using heuristics (length, keywords, ticker hints, etc.).

Summarization – Selected articles are mapped to key points (“map phase”), reduced to key insights (“reduce phase”), and summarized by an LLM.

Output – Produces a Markdown report summarizing the period and ticker with links to original articles.

📂 Directory Structure
finreport/
├── core/
│   ├── data/
│   │   ├── db.py                 # Database engine setup
│   ├── selectors/
│   │   ├── select_finance_yahoo.py  # Article selection logic
│   ├── summarize/
│   │   ├── map_reduce.py         # Map/reduce LLM summarization
│   ├── llm/
│   │   ├── llm.py                # Unified LLM interface (Mistral/OpenAI)
│
├── scripts/
│   ├── make_ticker_period_summary.py  # Generate ticker-based summary
│   ├── generate_report.py             # Earlier full-period report
│
├── build/                         # Generated markdown summaries
├── .env                           # Environment variables
└── README.md                      # (This file)

⚙️ Setup
1. Create and activate a virtual environment
python3 -m venv finreportenv
source finreportenv/bin/activate

2. Install dependencies
pip install -r requirements.txt


Typical dependencies include:
pandas, sqlalchemy, psycopg2, python-dotenv, mistralai, openai

3. Configure environment

Create a .env file in your project root (~/finreport/.env):

PG_DSN=postgresql:///finreport
MISTRAL_API_KEY=your_mistral_key_here
OPENAI_API_KEY=your_openai_key_here

🧩 Choosing Your LLM Provider

You can switch between Mistral and OpenAI backends via environment variables.

Option A — Mistral (default)
export LLM_PROVIDER=mistral
export MISTRAL_API_KEY=sk-...
export LLM_MODEL=mistral-small-latest

Option B — OpenAI
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export LLM_MODEL=gpt-4o-mini


These can be made persistent by adding them to .env.

🧠 Running a Summary Job

Generate a financial summary for a specific ticker and date range:

python -m scripts.make_ticker_period_summary 2025-10-02 2025-10-03 \
  --ticker NVDA \
  --max-articles 3 \
  --max-summary-chars 1500


Output:

✅ Wrote build/summary_NVDA_2025-10-02_2025-10-03.md
Selected articles: 3 | Consolidated bullets: 24

📝 Output Format

Example Markdown output (build/summary_NVDA_2025-10-02_2025-10-03.md):

# Ticker: NVDA
**Period:** [2025-10-02 → 2025-10-03]

---

## Summary

**NVIDIA (NVDA) Investor Summary — 2025-10-03**

NVIDIA reported strong Q3 2025 results, with revenue up 22% YoY to $24.3B, driven by record datacenter GPU demand and AI acceleration.  
Gross margin expanded to 71.5%, beating guidance...

*(998 characters)*

---

## Sources
- https://finance.yahoo.com/news/nvidia-ceo-jensen-huang-calls-095902235.html
- https://finance.yahoo.com/news/amazon-alexa-feature-impacts-nvidia-003700735.html

🔍 Current Limitations

Only Finance Yahoo articles are used.

Requires pre-populated news_raw PostgreSQL table.

Summary quality depends on selected LLM and token limits.

No UI yet — CLI only.

🧭 Roadmap

Near-term goals:

 Add reranking using vector similarity (e.g., keyword embeddings).

 Implement automatic title inference in Sources section.

 Add PDF export of generated summaries.

 Extend selectors to include Bloomberg, CNBC, or Reuters feeds.

 Optional sentiment scoring (bullish/bearish tone detection).

👤 Author

Philippe Damay
Singapore | LinkedIn

Finance & Technology Professional | Data, AI & Trading Analytics
