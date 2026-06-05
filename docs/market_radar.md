# Market Radar

`scripts/run_market_radar.py` builds a long-term research radar for preopen, intraday, and after-close market review.

It does not generate direct trading instructions. The output is a research artifact for reading market tone, theme breadth, big-money flow, ETF/futures/FX watch points, and Obsidian evidence classification.

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_market_radar.ps1 -Mode intraday
```

Mode can be `preopen`, `intraday`, or `after_close`. All modes write the same structured radar so the daily workflow can compare context before, during, and after the market session.

## Inputs

- `picks/cache/market_data_snapshot.json`
- `picks/cache/candidate_board.json`
- `picks/cache/flow_snapshot.json`
- `picks/cache/fiscal_ai_investment_news.json`

Kiwoom API can be attached later as the preferred intraday provider for current price, trading value, foreign/institution flow, KOSPI200 futures, program trading, and condition-search watch lists. Until then, the radar uses existing project snapshots.

## Output

`picks/cache/market_radar.json`

Main fields:

- `preopen`: day-framing checklist for US catalysts, futures/FX, ETF themes, and risk events
- `intraday`: research alerts such as `THEME_ACTIVE`, `WATCH_UP`, `RISK_DOWN`, and `NO_TRADE_CHASE`
- `after_close`: review questions for closing-price and confirmed-flow reconciliation
- `theme_flows[]`: theme breadth, average return, top ticker, foreign/institution 5-day flow
- `market_context`: watch slots for `futures`, `etf`, `fx_rates`, and `big_money`
- `obsi.evidence_map[]`: Obsidian classification hints for `artifact`, `research_fact`, `news`, and `analysis`

## Research Alert Semantics

- `THEME_ACTIVE`: multiple names in a theme show positive breadth
- `WATCH_UP`: positive move with elevated volume
- `RISK_DOWN`: sharp negative move requiring thesis/news review
- `NO_TRADE_CHASE`: hot move that should be marked as chase-risk, not a buy signal
- `DATA_STALE`: reserved for future provider freshness checks

These are evidence-routing labels for long-term research, not buy/sell signals.

## Obsidian Recording

Use `obsi` to split the radar into:

- `artifact`: `market_radar.json`, source snapshots, candidate board
- `research_fact`: price, change rate, volume ratio, RSI, foreign/institution flow
- `news`: Fiscal.ai and web catalysts
- `analysis`: theme breadth, risk interpretation, after-close review
- `report`: final preopen/intraday/after-close summary
