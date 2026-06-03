#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Filter US-close Korea preopen candidates with Korean market snapshot data.

Outputs:
  picks/cache/preopen_filtered_candidates.json
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANDIDATES = ROOT / "picks" / "cache" / "preopen_candidates.json"
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "preopen_filtered_candidates.json"
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def read_json(path: Path) -> Dict[str, Any]:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def market_by_ticker(market: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Index market snapshot items by ticker."""
    return {str(item.get("ticker", "")).zfill(6): item for item in market.get("items", [])}


def parse_stop_pct(text: str) -> Optional[float]:
    """Extract a negative stop percentage from Korean condition text."""
    match = re.search(r"-(\d+(?:\.\d+)?)\s*%", text)
    if not match:
        return None
    return float(match.group(1))


def risk_reward_from_stop(gap_pct: Optional[float], stop_pct: Optional[float]) -> Optional[float]:
    """Estimate rough risk/reward from US score and stop distance."""
    if gap_pct is None or stop_pct in (None, 0):
        return None
    upside_proxy = max(3.0, 6.0 - max(gap_pct, 0.0))
    return round(upside_proxy / float(stop_pct), 4)


def decision_for_candidate(candidate: Dict[str, Any], market_item: Optional[Dict[str, Any]], require_foreign: bool) -> Dict[str, Any]:
    """Filter one candidate."""
    ticker = str(candidate.get("ticker", "")).zfill(6)
    name = candidate.get("name", ticker)
    result: Dict[str, Any] = {
        "ticker": ticker,
        "name": name,
        "sector": candidate.get("sector"),
        "us_score": candidate.get("score"),
        "drivers": candidate.get("drivers", []),
        "foreign_flow_status": "unknown",
        "foreign_intensity": "unknown",
        "price": None,
        "gap_pct": None,
        "risk_reward": None,
        "decision": "PASS",
        "reason": "",
        "entry_condition": candidate.get("entry_condition"),
        "stop_condition": candidate.get("stop_condition"),
    }

    if market_item is None:
        result["decision"] = "PASS"
        result["reason"] = "market_price_missing"
        return result

    price = market_item.get("price")
    gap_pct = market_item.get("change_rate")
    result["price"] = price
    result["gap_pct"] = gap_pct
    result["market_source"] = market_item.get("primary_source")

    if gap_pct is not None and float(gap_pct) >= 5:
        result["decision"] = "BLOCK"
        result["reason"] = "gap_over_5pct"
        return result

    stop_pct = parse_stop_pct(str(candidate.get("stop_condition", "")))
    result["risk_reward"] = risk_reward_from_stop(float(gap_pct or 0), stop_pct)
    if result["risk_reward"] is not None and result["risk_reward"] < 1.5:
        result["decision"] = "BLOCK"
        result["reason"] = "risk_reward_below_1_5"
        return result

    if require_foreign:
        result["decision"] = "NEEDS_FOREIGN_CONFIRMATION"
        result["reason"] = "foreign_flow_not_available"
        return result

    result["decision"] = "WATCH"
    result["reason"] = "price_gap_passed_foreign_not_required"
    return result


def offline_market_snapshot() -> Dict[str, Any]:
    """Return deterministic market data for tests."""
    return {
        "generated_at": now_kst(),
        "market": "KR",
        "mode": "offline_sample",
        "items": [
            {"ticker": "000660", "name": "SK하이닉스", "price": 2360000, "change_rate": 2.8, "primary_source": "offline_fixture"},
            {"ticker": "240810", "name": "원익IPS", "price": 45500, "change_rate": 2.2, "primary_source": "offline_fixture"},
            {"ticker": "007660", "name": "이수페타시스", "price": 136300, "change_rate": 6.1, "primary_source": "offline_fixture"},
        ],
    }


def run(args: argparse.Namespace) -> Dict[str, Any]:
    """Run the preopen filter."""
    candidates = read_json(Path(args.candidates_path))
    market = offline_market_snapshot() if args.offline_sample else read_json(Path(args.market_snapshot_path))
    by_ticker = market_by_ticker(market)
    filtered = [
        decision_for_candidate(candidate, by_ticker.get(str(candidate.get("ticker", "")).zfill(6)), args.require_foreign)
        for candidate in candidates.get("preopen_candidates", [])
    ]
    final_candidates = [
        item for item in filtered
        if item["decision"] in {"WATCH", "NEEDS_FOREIGN_CONFIRMATION"}
    ][:3]
    blocked = [item for item in filtered if item["decision"] == "BLOCK"]
    passed = [item for item in filtered if item["decision"] == "PASS"]
    return {
        "generated_at": now_kst(),
        "mode": "offline_sample" if args.offline_sample else "live",
        "source": "preopen_candidates+market_data_snapshot",
        "require_foreign": args.require_foreign,
        "market_snapshot_generated_at": market.get("generated_at"),
        "input_candidates_generated_at": candidates.get("generated_at"),
        "final_candidates": final_candidates,
        "blocked": blocked,
        "passed": passed,
        "hard_blocks": [
            "gap_pct >= 5 blocks chasing",
            "risk_reward < 1.5 blocks entry",
            "foreign flow unknown cannot become FOCUS",
        ],
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Filter Korea preopen candidates.")
    parser.add_argument("--candidates-path", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--require-foreign", action="store_true", default=True)
    parser.add_argument("--allow-foreign-unknown", action="store_false", dest="require_foreign")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        result = run(args)
        write_json(Path(args.output_path), result)
        print(f"wrote {args.output_path}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
