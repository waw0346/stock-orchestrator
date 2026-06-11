from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_json(args: list[str]) -> dict:
    completed = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
    return json.loads(completed.stdout)


def test_bootstrap_dry_run() -> None:
    data = run_json([sys.executable, "scripts/bootstrap.py", "--dry-run", "--json"])
    assert data["python"]["ok"], data["python"]
    assert data["requirements_present"]
    assert "pydantic" in {item["name"] for item in data["packages"]}


def test_context_summary_projection() -> None:
    data = run_json([
        sys.executable,
        "scripts/summarize_context.py",
        "--ticker",
        "012450",
        "--purpose",
        "risk",
        "--max-items",
        "1",
        "--max-chars",
        "500",
    ])
    assert data["ticker"] == "012450"
    assert data["purpose"] == "risk"
    assert data["token_control"]["max_items_per_cache"] == 1
    assert data["index_rows"]


def main() -> int:
    test_bootstrap_dry_run()
    test_context_summary_projection()
    print("cross-platform smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
