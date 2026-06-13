# Context Summary Command

`scripts/summarize_context.py` creates a small ticker-focused JSON projection from large operating files under `picks/` and `picks/cache/`.

Use it before asking an agent to analyze a ticker when full cache files would be too large for the prompt.

```powershell
python scripts\summarize_context.py --ticker 012450 --purpose risk
python scripts\summarize_context.py --ticker 012450 --purpose flow --max-items 2
python scripts\summarize_context.py --ticker 012450 --purpose market --output-path picks\cache\context_summary.test.json
```

Purposes:

- `risk`: fundamentals, market snapshot, candidate board, market radar, Fiscal.ai news
- `flow`: flow snapshots, foreign streaks, flow-volume candidates, flow comparison
- `market`: market snapshot, market radar, candidate board, pullback and preopen candidates
- `all`: union of the above

Token rule:

- Do not paste full DART/news/cache payloads into agent prompts.
- Pass this summary JSON plus only the specific source link or file path needed for audit.
- Increase `--max-items` or `--max-chars` only when a reviewer needs more evidence.

Runtime rule:

- If an AI runtime lacks subagents, pass this projection to the focused role prompt instead of copying operating cache files.
