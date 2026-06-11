# AI Runtime Contract

This project can be operated by different AI coding environments. Treat Claude Code subagents, Codex tools, browser/search tools, and plain CLI scripts as adapters around the same core workflow.

## Core Rules

- Read `CURRENT_STATE.md`, `CLAUDE.md`, and `INVESTMENT_POLICY.md` before changing operating logic.
- Prefer local scripts and cache projections over pasting large files into prompts.
- Use `python scripts/summarize_context.py --ticker <ticker> --purpose risk|flow|market` before ticker-level agent analysis.
- Do not paste full DART, news, or `picks/cache/*.json` payloads into an agent prompt.
- Run `python scripts/bootstrap.py --dry-run --json` in new environments before running the full suite.
- If PowerShell is unavailable, run `python tests/run_cross_platform_smoke.py` as the portable minimum check.

## Tool Mapping

- Search web: use the current runtime's web search/browser/search API.
- Fetch page: use the current runtime's browser/fetch tool.
- Read file: use filesystem read commands or the runtime's file reader.
- Write file: use patch-based edits when available.
- Subagent: use Claude subagents when available; otherwise create a focused prompt using the matching `.claude/agents/*.md` role file.
- MCP provider: use MCP when available; otherwise use the local collector scripts and cached JSON snapshots.

## Verification

- Full Windows/PowerShell suite: `powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_all_tests.ps1`
- Portable smoke suite: `python tests/run_cross_platform_smoke.py`
- Bootstrap dry run: `python scripts/bootstrap.py --dry-run --json`
