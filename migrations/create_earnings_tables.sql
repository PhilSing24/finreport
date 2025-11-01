-- Create earnings_calls table
CREATE TABLE earnings_calls (
    -- Identity
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    fiscal_quarter TEXT NOT NULL,
    fiscal_year INTEGER NOT NULL,
    
    -- Timing (UTC)
    call_date DATE NOT NULL,
    call_start_utc TIMESTAMP NOT NULL,
    
    -- Content
    full_transcript TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create call_interventions table
CREATE TABLE call_interventions (
    -- Identity
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES earnings_calls(id),
    
    -- Timing
    timestamp_utc TIMESTAMP NOT NULL,
    relative_seconds INTEGER NOT NULL,
    
    -- Speaker
    speaker_name TEXT NOT NULL,
    speaker_role TEXT,
    
    -- Content
    text TEXT NOT NULL,
    sequence_order INTEGER NOT NULL
);

-- Indexes
CREATE INDEX idx_earnings_ticker ON earnings_calls(ticker, call_date);
CREATE INDEX idx_interventions_call ON call_interventions(call_id);
CREATE INDEX idx_interventions_time ON call_interventions(timestamp_utc);
