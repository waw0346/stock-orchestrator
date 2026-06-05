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

## Kiwoom Provider

`scripts/collect_kiwoom_foreign_rank.py` fills `foreign_flow_history.csv` from Kiwoom REST API foreign net-buy rank data.

It uses Kiwoom domestic stock rank API `ka10034` (`외인기간별매매상위요청`) through `/api/dostk/rkinfo`.

Required environment variables:

| variable | meaning |
|----------|---------|
| `KIWOOM_APP_KEY` | Kiwoom REST API app key |
| `KIWOOM_APP_SECRET` | Kiwoom REST API app secret |
| `KIWOOM_ACCESS_TOKEN` | Optional pre-issued access token |
| `KIWOOM_BASE_URL` | Optional base URL. Defaults to `https://api.kiwoom.com` |

Run live collection:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_kiwoom_foreign_rank.ps1 `
  -OutputCsvPath picks\cache\foreign_flow_history.csv `
  -SnapshotPath picks\cache\foreign_rank_snapshot.json `
  -Top 20
```

Then run the streak scanner:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\find_foreign_streaks.ps1 `
  -InputCsvPath picks\cache\foreign_flow_history.csv `
  -OutputPath picks\cache\foreign_streak_candidates.json
```

Network-free verification:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\collect_kiwoom_foreign_rank.ps1 `
  -OfflineSample `
  -OutputCsvPath picks\cache\foreign_flow_history.kiwoom.test.csv `
  -SnapshotPath picks\cache\foreign_rank_snapshot.kiwoom.test.json
```

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
