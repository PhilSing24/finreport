-- Add press release columns to news_raw
ALTER TABLE news_raw 
ADD COLUMN IF NOT EXISTS is_press_release BOOLEAN DEFAULT FALSE;

ALTER TABLE news_raw 
ADD COLUMN IF NOT EXISTS press_release_type TEXT;

ALTER TABLE news_raw 
ADD COLUMN IF NOT EXISTS related_call_id TEXT REFERENCES earnings_calls(id);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_news_press_releases 
ON news_raw(is_press_release, press_release_type) 
WHERE is_press_release = TRUE;

CREATE INDEX IF NOT EXISTS idx_news_related_call 
ON news_raw(related_call_id) 
WHERE related_call_id IS NOT NULL;

-- Add comments
COMMENT ON COLUMN news_raw.is_press_release IS 'TRUE if this is an official company press release';
COMMENT ON COLUMN news_raw.press_release_type IS 'Type: earnings, product, partnership, guidance, etc.';
COMMENT ON COLUMN news_raw.related_call_id IS 'Links press release to earnings call if applicable';
