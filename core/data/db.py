# core/data/db.py
import os
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Load environment variables from ~/finreport/.env
load_dotenv(Path.home() / "finreport" / ".env")

# PostgreSQL connection string (from .env or default local)
PG_DSN = os.getenv("PG_DSN", "postgresql:///finreport")

# Create SQLAlchemy engine
engine = create_engine(PG_DSN)

