-- migrations/align_with_tiingo_api.sql
--
-- Align news_raw schema with Tiingo API field names
--
-- Run with:
--   psql -d finreport -f migrations/align_with_tiingo_api.sql

BEGIN;

-- Rename columns to match Tiingo API
ALTER TABLE news_raw RENAME COLUMN article_url TO url;
ALTER TABLE news_raw RENAME COLUMN keywords TO tags;

-- Change publisher from JSONB to TEXT (storing just the domain name)
-- First, extract the name field if it's currently JSONB
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'news_raw' 
        AND column_name = 'publisher'
        AND data_type = 'jsonb'
    ) THEN
        -- Extract publisher.name to temporary column
        ALTER TABLE news_raw ADD COLUMN source TEXT;
        UPDATE news_raw SET source = publisher->>'name';
        ALTER TABLE news_raw DROP COLUMN publisher;
    ELSE
        -- If it's already TEXT, just rename
        ALTER TABLE news_raw RENAME COLUMN publisher TO source;
    END IF;
END $$;

-- Add crawl_date if it doesn't exist (not currently captured, but useful for future)
ALTER TABLE news_raw ADD COLUMN IF NOT EXISTS crawl_date TIMESTAMP WITH TIME ZONE;

-- Update comments
COMMENT ON COLUMN news_raw.url IS 'Article URL from Tiingo API';
COMMENT ON COLUMN news_raw.source IS 'News source domain (e.g., finance.yahoo.com)';
COMMENT ON COLUMN news_raw.tags IS 'Tags from Tiingo proprietary tagging algorithm';
COMMENT ON COLUMN news_raw.crawl_date IS 'When Tiingo added this article to their database (UTC)';

-- Verify the changes
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_name = 'news_raw'
ORDER BY ordinal_position;

COMMIT;