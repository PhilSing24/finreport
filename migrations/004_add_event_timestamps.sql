-- Add detailed timestamps to earnings_calls
ALTER TABLE earnings_calls
ADD COLUMN IF NOT EXISTS press_release_time_utc TIMESTAMPTZ;

ALTER TABLE earnings_calls
ADD COLUMN IF NOT EXISTS call_end_utc TIMESTAMPTZ;

COMMENT ON COLUMN earnings_calls.press_release_time_utc IS 'When earnings press release was published (from RSS/newswire)';
COMMENT ON COLUMN earnings_calls.call_end_utc IS 'When earnings call ended';

CREATE INDEX IF NOT EXISTS idx_earnings_pr_time 
ON earnings_calls(press_release_time_utc);
