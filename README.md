# aifinreport 🤖📊

AI-powered financial news report generator using LLMs (Mistral/OpenAI) to create investor summaries from Yahoo Finance articles.

## Features

- 📰 Fetches financial news from Tiingo API
- 🎯 Intelligent article selection with MMR diversity
- 🤖 LLM-powered summarization (map-reduce approach)
- 📊 Generates concise investor reports
- 🔄 Supports both Mistral and OpenAI APIs

## Installation

git clone https://github.com/PhilSing24/finreport.git
cd finreport
python3 -m venv venv
source venv/bin/activate
pip install -e .
cp .env.example .env

## Usage

python src/aifinreport/cli/generate_report.py 2025-10-01 2025-10-06 --ticker NVDA

Reports are saved to outputs/ directory.

## Project Structure

src/aifinreport/ - Main package with cli, ingestion, analysis, llm, and database modules

## Author

Philippe Damay
