# Flow Streak Scanner

`scripts/run_flow_analysis.py` is a comprehensive flow scanner that identifies 3-day consecutive buying and selling streaks for both foreign investors and pension funds.

It uses the Kiwoom REST API to query:
- Foreigner rankings via `ka10034` (dt date-based)
- Pension fund rankings via `ka10044` (strt_dt/end_dt date-based)

It will generate the top 5 candidates for:
1. Foreigner 3-day consecutive buying
2. Foreigner 3-day consecutive selling
3. Pension Fund 3-day consecutive buying
4. Pension Fund 3-day consecutive selling

## Setup & Environment Variables

Required variables in `.env.local` or process environment:
- `KIWOOM_APP_KEY`: Kiwoom REST API application key.
- `KIWOOM_APP_SECRET`: Kiwoom REST API secret key.
- `KIWOOM_ACCESS_TOKEN`: Pre-issued access token (will be cleared if invalid).
- `KIWOOM_BASE_URL`: Optional custom base URL (default: `https://api.kiwoom.com`).

## Running the Scanner

### Live Scan

Execute the PowerShell wrapper `scripts/run_flow_analysis.ps1` to run the scanner:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_analysis.ps1
```

Options:
- `-TopLimit`: Number of rank items to query from Kiwoom API per day (default: 100).
- `-OutputPath`: Output path for JSON result (default: `picks/cache/flow_streak_candidates.json`).

### Offline / Mock Scan

Verify scanner logic without sending live API requests:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_flow_analysis.ps1 -OfflineSample
```

## Outputs

The results are saved in JSON format:
- `picks/cache/flow_streak_candidates.json`

Important fields:
- `generated_at`: Timestamp of analysis.
- `dates_analyzed`: The 3 trading dates selected for consecutive analysis.
- `foreign_buy_candidates`: List of tickers with 3-day consecutive foreign buying.
- `foreign_sell_candidates`: List of tickers with 3-day consecutive foreign selling.
- `pension_buy_candidates`: List of tickers with 3-day consecutive pension fund buying.
- `pension_sell_candidates`: List of tickers with 3-day consecutive pension fund selling.

For each candidate, the scanner reports:
- `ticker`: Stock ticker
- `name`: Stock name
- `consecutive_days`: Streak length (always 3)
- `close`: Last close price
- `net_flow_sum`: Total net flow sum over 3 days (quantity or amount)
- `latest_net_flow`: Flow in the most recent trading date
