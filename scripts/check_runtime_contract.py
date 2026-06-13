from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class TextContract:
    path: str
    required: tuple[str, ...]


REQUIRED_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "CURRENT_STATE.md",
    "INVESTMENT_POLICY.md",
    "docs/ai_runtime_adapter.md",
    "docs/context_summary.md",
    "scripts/bootstrap.py",
    "scripts/summarize_context.py",
    "tests/run_cross_platform_smoke.py",
)

TEXT_CONTRACTS = (
    TextContract(
        "AGENTS.md",
        (
            "AI Runtime Contract",
            "Read `CURRENT_STATE.md`, `CLAUDE.md`, and `INVESTMENT_POLICY.md`",
            "python scripts/summarize_context.py --ticker <ticker> --purpose risk|flow|market",
            "python scripts/bootstrap.py --dry-run --json",
            "python tests/run_cross_platform_smoke.py",
        ),
    ),
    TextContract(
        "CLAUDE.md",
        (
            "AGENTS.md",
            "docs/ai_runtime_adapter.md",
            "scripts/summarize_context.py",
        ),
    ),
    TextContract(
        "docs/ai_runtime_adapter.md",
        (
            "Runtime Layers",
            "Prompt Portability",
            "Never treat cached data as live",
            "scripts/summarize_context.py",
        ),
    ),
    TextContract(
        "docs/context_summary.md",
        (
            "Do not paste full DART/news/cache payloads",
            "Token rule",
            "--purpose risk",
        ),
    ),
    TextContract(
        "README.md",
        (
            "python scripts/bootstrap.py --dry-run --json",
            "python tests/run_cross_platform_smoke.py",
            "AGENTS.md",
            "docs\\ai_runtime_adapter.md",
        ),
    ),
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required_files() -> list[str]:
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            errors.append(f"missing required runtime file: {relative}")
    return errors


def check_text_contracts() -> list[str]:
    errors: list[str] = []
    for contract in TEXT_CONTRACTS:
        path = ROOT / contract.path
        if not path.exists():
            errors.append(f"missing contract file: {contract.path}")
            continue
        text = read_text(path)
        for required in contract.required:
            if required not in text:
                errors.append(f"{contract.path} missing required text: {required}")
    return errors


def check_runtime_flow() -> list[str]:
    warnings: list[str] = []
    smoke = ROOT / "tests/run_cross_platform_smoke.py"
    if smoke.exists() and "scripts/check_runtime_contract.py" not in read_text(smoke):
        warnings.append("portable smoke suite should run scripts/check_runtime_contract.py")

    run_all = ROOT / "tests/run_all_tests.ps1"
    if run_all.exists() and "runtime contract tests" not in read_text(run_all):
        warnings.append("full test suite should include runtime contract tests")

    return warnings


def build_report() -> dict[str, Any]:
    errors = check_required_files() + check_text_contracts()
    warnings = check_runtime_flow()
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "required_files": list(REQUIRED_FILES),
        "contracts_checked": [contract.path for contract in TEXT_CONTRACTS],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the portable AI runtime contract.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("AI runtime contract: " + ("ok" if report["ok"] else "failed"))
        for error in report["errors"]:
            print("ERROR " + error)
        for warning in report["warnings"]:
            print("WARN " + warning)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
