# Data Directory

## earnings_transcripts/

Stores earnings call transcripts in plain text format.

### Structure:
```
earnings_transcripts/
├── NVDA/
│   └── NVDA_Q2_FY2026_2025-08-27.txt
├── TSLA/
└── {TICKER}/
```

### Naming Convention:
`{TICKER}_{QUARTER}_{FISCAL_YEAR}_{DATE}.txt`

Examples:
- NVDA_Q2_FY2026_2025-08-27.txt
- TSLA_Q3_FY2025_2025-10-23.txt

### Sources:
- Yahoo Finance transcripts
- Manual uploads

### Notes:
- All transcripts in plain text (.txt) format
- Keep original timestamps and speaker names
- One file per earnings call
