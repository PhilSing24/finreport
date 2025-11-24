-- Standardize all timestamp columns to use 'timestamp with time zone'

-- Fix earnings_calls.call_start_utc
ALTER TABLE earnings_calls 
ALTER COLUMN call_start_utc 
TYPE timestamp with time zone 
USING call_start_utc AT TIME ZONE 'UTC';

-- Add comment
COMMENT ON COLUMN earnings_calls.call_start_utc IS 'Call start time in UTC (timestamptz)';
