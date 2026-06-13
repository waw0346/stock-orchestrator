# AI Runtime Adapter

The repository has a Claude Code heritage, but its operating contract should remain portable across AI environments.

Use `AGENTS.md` as the shared contract. Runtime-specific instructions should translate tool names and capabilities without changing the workflow order, cache rules, or verification gates.

## Runtime Layers

| Layer | Portable contract | Claude Code adapter | Generic fallback |
| --- | --- | --- | --- |
| Role routing | Select the right analyst role | `.claude/agents/*.md` subagents | Read the matching role file and run it as a focused prompt |
| Web search | Current market/news lookup | `WebSearch` | Browser/search API, search connector, or manual source lookup |
| Page fetch | Inspect source pages | `WebFetch` | Browser/fetch tool or local downloaded source |
| File read | Inspect repo files | `Read` | Shell/file read command |
| File write | Patch repo files | `Write` | Patch tool or safe editor operation |
| DART/provider data | Structured financial/corporate data | PlayMCP/OpenDART MCP | `scripts/collect_fundamentals.py` and cache snapshots |
| Context compression | Small task-specific input | Agent summary handoff | `scripts/summarize_context.py` |
| Verification | Repeatable checks | PowerShell suite | `python tests/run_cross_platform_smoke.py` |

## Environment Bootstrap

Use this in a new machine, CI runner, or AI sandbox:

```bash
python scripts/bootstrap.py --dry-run --json
python scripts/check_runtime_contract.py --json
python -m pip install -r requirements.txt
python tests/run_cross_platform_smoke.py
```

Windows full validation:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tests\run_all_tests.ps1
```

## Prompt Portability

When a `.claude/agents/*.md` file says `WebSearch`, `WebFetch`, `Read`, or `Write`, translate that to the equivalent capability in the current runtime. If the capability does not exist, state the missing capability and continue from cached/local data with lower confidence.

When a workflow says "subagent", either use a real subagent/thread or run the relevant role prompt in a separate focused context. The important contract is role isolation and structured JSON output, not the specific product feature.

## Data Portability

Provider availability varies by runtime. Prefer this order:

1. Fresh provider data through MCP/API when available.
2. Local collector scripts with explicit offline/sample mode when testing.
3. Existing `picks/cache` snapshots with generated timestamps and lower confidence.

Never treat cached data as live unless its timestamp and provider status support that claim.
