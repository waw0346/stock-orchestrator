# Foreign Streak Scanner

`scripts/find_foreign_streaks.py` finds Korean stocks that show a 3-day consecutive foreign net-buy streak after the market close.

## Input

Default input:

`picks/cache/foreign_flow_history.csv`

Required CSV columns:

| column | meaning |
|--------|---------|
| `date` | Trading date, preferably `YYYY-MM-DD` |
| `ticker` | Six-digit Korean ticker |
| `foreign_net_buy` | Foreign investor net buy amount or shares |

Optional columns:

| column | meaning |
|--------|---------|
| `name` | Stock name |
| `institution_net_buy` | Institution net buy amount or shares |
| `close` | Close price |
| `volume` | Volume |

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\find_foreign_streaks.ps1 `
  -InputCsvPath picks\cache\foreign_flow_history.csv `
  -OutputPath picks\cache\foreign_streak_candidates.json `
  -MinConsecutiveDays 3 `
  -Top 20
```

## Output

Default output:

`picks/cache/foreign_streak_candidates.json`

Important fields:

- `candidates[].consecutive_foreign_buy_days`
- `candidates[].foreign_net_buy_sum`
- `candidates[].institution_net_buy_sum`
- `summary.candidate_count`

## Operating Rule

Use this after KRX close, once investor flow data has settled. A stock passes the first gate only when it has a 3-day consecutive foreign net-buy streak ending on the latest available row for that ticker.

The output is a screening list, not a trading instruction. Feed the strongest names into `WATCHLIST.md`, `preopen-foreign-scanner`, or `candidate_board.json` review only after checking price gap, valuation, and risk/reward gates.
