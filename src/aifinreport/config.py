"""Central configuration for aifinreport."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
PROJECT_ROOT = Path(__file__).resolve().parents[2]  # finreport/
load_dotenv(PROJECT_ROOT / ".env")

# Paths
BUILD_DIR = PROJECT_ROOT / "outputs"
BUILD_DIR.mkdir(parents=True, exist_ok=True)

# Database
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mistral").lower()
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "mistral-small-latest")
LLM_MISTRAL_FALLBACKS = [
    m.strip() for m in os.getenv(
        "LLM_MISTRAL_FALLBACKS",
        "mistral-medium-latest,mistral-large-latest"
    ).split(",") if m.strip()
]

# Tiingo API
TIINGO_API_TOKEN = os.getenv("TIINGO_API_TOKEN")

# Tolerances
LENGTH_TOLERANCE = 0.10
