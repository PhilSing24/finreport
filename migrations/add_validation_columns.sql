-- migrations/add_validation_columns.sql
-- 
-- SQL migration to add validation columns to news_raw table.
--
-- Run this before using the updated ingestion code:
--   psql -d finreport -f migrations/add_validation_columns.sql
--
-- Or from Python:
--   python -c "from core.data.db import engine; from sqlalchemy import text; engine.execute(text(open('migrations/add_validation_columns.sql').read()))"

-- Add validation columns if they don't exist
ALTER TABLE news_raw 
  ADD COLUMN IF NOT EXISTS validation_status TEXT,
  ADD COLUMN IF NOT EXISTS validation_reason TEXT;

-- Create index for faster validation queries
CREATE INDEX IF NOT EXISTS idx_news_raw_validation_status 
  ON news_raw(validation_status);

-- Create index for validation reason filtering
CREATE INDEX IF NOT EXISTS idx_news_raw_validation_reason 
  ON news_raw(validation_reason);

-- Add comments for documentation
COMMENT ON COLUMN news_raw.validation_status IS 
  'Content validation status: passed, failed, or null (not validated)';

COMMENT ON COLUMN news_raw.validation_reason IS 
  'Reason for validation result: ticker_in_title, ticker_in_description, ticker_in_url, no_mention_of_TICKER, title_mentions_different_ticker_XXX, etc.';