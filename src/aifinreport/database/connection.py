"""Database connection using SQLAlchemy."""
from sqlalchemy import create_engine
from aifinreport.config import PG_DSN

# Create SQLAlchemy engine
engine = create_engine(PG_DSN)
