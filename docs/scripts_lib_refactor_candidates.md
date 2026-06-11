# scripts/lib Refactor Candidates

This note ranks low-risk places to apply `scripts/lib` helpers after the portable runtime work.

## Priority 1: Shared JSON I/O

Good candidates:

- `scripts/run_candidate_board.py`
- `scripts/run_market_radar.py`
- `scripts/run_preopen_filter.py`
- `scripts/run_pullback_screen.py`
- `scripts/collect_flow_data.py`

Reason: these scripts already have small `read_json` and `write_json` helpers with similar behavior. Replacing them with `scripts.lib.io.read_json` and `write_json` should be mechanical and easy to verify with existing offline/integration tests.

## Priority 2: Env File Reader

Good candidates:

- `scripts/check_fiscal_ai.py`
- `scripts/collect_fiscal_ai.py`
- `scripts/collect_fundamentals.py`

Reason: all parse `.env.local` style files. Move them to `scripts.lib.env.read_env_file_value` after confirming quote handling stays compatible.

## Priority 3: Ticker Universe Parsing

Good candidates:

- `scripts/collect_market_data.py`
- `scripts/collect_fundamentals.py`
- `scripts/run_pullback_screen.py`

Reason: these scripts parse `picks/INDEX.md`, paper rules, market snapshots, and preopen candidates. The logic is more business-sensitive than JSON I/O, so migrate after adding focused tests for active/watch/closed/completed status handling.

## Defer

- Kiwoom live API scripts
- `run_vwap_accumulation_screener.py`
- `run_weekly_flow_momentum_update.ps1`

Reason: these have more domain-specific behavior, external state, or large report generation logic. Refactor only after the shared helpers are stable in lower-risk scripts.

## Verification Per Migration

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_all_tests.ps1
python tests\run_cross_platform_smoke.py
```

For candidate board, market radar, preopen, and pullback changes, also inspect the generated `.test.json` files only when a test fails. Do not paste full cache payloads into agent prompts; use `scripts/summarize_context.py` for projection.
