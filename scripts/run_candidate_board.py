#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Build a consolidated candidate board from preopen, pullback, fundamentals, and market snapshots.

Outputs:
  picks/cache/candidate_board.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_PULLBACK = ROOT / "picks" / "cache" / "pullback_candidates.json"
DEFAULT_PREOPEN = ROOT / "picks" / "cache" / "preopen_filtered_candidates.json"
DEFAULT_FUNDAMENTALS = ROOT / "picks" / "cache" / "fundamentals_snapshot.json"
DEFAULT_FISCAL_AI_NEWS = ROOT / "picks" / "cache" / "fiscal_ai_investment_news.json"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "candidate_board.json"
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
    """Read JSON if present, otherwise return empty dict."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(f"WARN: Corrupted or empty JSON file: {path}. Returning empty dict.", file=sys.stderr)
        return {}


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def by_ticker(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index items by six-digit ticker."""
    return {str(item.get("ticker", "")).zfill(6): item for item in items if item.get("ticker")}


def collect_preopen_items(preopen: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Flatten preopen final/blocked/passed items by ticker."""
    result: Dict[str, Dict[str, Any]] = {}
    for section in ("final_candidates", "blocked", "passed"):
        for item in preopen.get(section, []) or []:
            row = dict(item)
            row["section"] = section
            result[str(item.get("ticker", "")).zfill(6)] = row
    return result


def score_row(preopen: Optional[Dict[str, Any]], pullback: Optional[Dict[str, Any]], fundamentals: Optional[Dict[str, Any]], market: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Score one ticker with conservative gates including valuation checks."""
    checks = {
        "preopen": preopen.get("decision") if preopen else None,
        "pullback": pullback.get("decision") if pullback else None,
        "fundamentals": "OK" if fundamentals and fundamentals.get("ok") else ("MISSING" if not fundamentals else "FAIL"),
        "market": "OK" if market and market.get("price") is not None else "MISSING",
    }
    block_reasons: List[str] = []
    score = 0

    if checks["market"] == "OK":
        score += 1
    else:
        block_reasons.append("market_missing")

    if checks["fundamentals"] == "OK":
        score += 2
    else:
        block_reasons.append("fundamentals_missing_or_failed")

    if checks["pullback"] in {"STRONG_ENTRY", "PROBE_ENTRY"}:
        score += 3
    elif checks["pullback"] == "WAIT":
        score += 1
    elif checks["pullback"] == "BLOCK":
        block_reasons.append("pullback_block")

    if checks["preopen"] in {"WATCH", "NEEDS_FOREIGN_CONFIRMATION"}:
        score += 2
    elif checks["preopen"] == "BLOCK":
        block_reasons.append("preopen_block")

    # Valuation checks from enriched fundamentals
    valuation: Dict[str, Any] = {}
    if fundamentals and fundamentals.get("ok"):
        per = fundamentals.get("per")
        pbr = fundamentals.get("pbr")
        eps = fundamentals.get("eps")
        market_cap = fundamentals.get("market_cap")
        week52_high = fundamentals.get("week52_high")
        week52_low = fundamentals.get("week52_low")
        enriched = fundamentals.get("valuation_fields_available", False)

        if per is not None:
            valuation["per"] = per
        if pbr is not None:
            valuation["pbr"] = pbr
        if eps is not None:
            valuation["eps"] = eps
        if market_cap is not None:
            valuation["market_cap"] = market_cap
        if week52_high is not None:
            valuation["week52_high"] = week52_high
        if week52_low is not None:
            valuation["week52_low"] = week52_low

        # Extreme valuation → BLOCK
        if per is not None and per > 100:
            block_reasons.append("valuation_per_extreme")
        elif per is not None and per > 50:
            checks["valuation"] = "WARN"
        if pbr is not None and pbr > 10:
            block_reasons.append("valuation_pbr_extreme")
        elif pbr is not None and pbr > 5:
            checks["valuation"] = "WARN"
        # Negative EPS (loss-making)
        if eps is not None and eps < 0:
            if checks.get("valuation") != "WARN":
                checks["valuation"] = "WARN"

        # Enriched valuation bonus
        if enriched and per is not None and pbr is not None:
            score += 1
            if checks.get("valuation") is None:
                checks["valuation"] = "OK"

    if block_reasons:
        decision = "BLOCK"
    elif score >= 7:
        decision = "FOCUS"
    elif score >= 4:
        decision = "WATCH"
    else:
        decision = "PASS"

    result = {
        "score": score,
        "decision": decision,
        "checks": checks,
        "block_reasons": block_reasons,
    }
    if valuation:
        result["valuation"] = valuation
    return result


def collect_us_catalysts(fiscal_ai_news: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent Fiscal.ai news as board-level US market context."""
    catalysts = []
    for item in fiscal_ai_news.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        catalysts.append({
            "company_key": item.get("company_key"),
            "event_type": item.get("event_type"),
            "importance": item.get("importance"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "source_url": item.get("source_url"),
            "collected_at": item.get("collected_at"),
        })
    catalysts.sort(key=lambda item: (str(item.get("collected_at") or ""), -int(item.get("importance") or 0)), reverse=True)
    return catalysts[:limit]


def run(args: argparse.Namespace) -> Dict[str, Any]:
    """Build consolidated board."""
    market = read_json(Path(args.market_snapshot_path))
    pullback = read_json(Path(args.pullback_path))
    preopen = read_json(Path(args.preopen_filtered_path))
    fundamentals = read_json(Path(args.fundamentals_path))
    fiscal_ai_news = read_json(Path(args.fiscal_ai_news_path))

    market_by_ticker = by_ticker(market.get("items", []))
    pullback_by_ticker = by_ticker(pullback.get("candidates", []))
    preopen_by_ticker = collect_preopen_items(preopen)
    fundamentals_by_ticker = by_ticker(fundamentals.get("items", []))

    tickers = sorted(set(market_by_ticker) | set(pullback_by_ticker) | set(preopen_by_ticker) | set(fundamentals_by_ticker))
    rows = []
    for ticker in tickers:
        market_item = market_by_ticker.get(ticker)
        pullback_item = pullback_by_ticker.get(ticker)
        preopen_item = preopen_by_ticker.get(ticker)
        fundamentals_item = fundamentals_by_ticker.get(ticker)
        scored = score_row(preopen_item, pullback_item, fundamentals_item, market_item)
        name = (
            (market_item or {}).get("name")
            or (pullback_item or {}).get("name")
            or (preopen_item or {}).get("name")
            or (fundamentals_item or {}).get("name")
            or ticker
        )
        rows.append({
            "ticker": ticker,
            "name": name,
            "price": (market_item or {}).get("price"),
            "change_rate": (market_item or {}).get("change_rate"),
            **scored,
        })

    rows.sort(key=lambda item: (item["decision"] != "FOCUS", item["decision"] != "WATCH", -item["score"], item["ticker"]))
    return {
        "generated_at": now_kst(),
        "source": "market+pullback+preopen+fundamentals+fiscal_ai_news",
        "inputs": {
            "market_generated_at": market.get("generated_at"),
            "pullback_generated_at": pullback.get("generated_at"),
            "preopen_generated_at": preopen.get("generated_at"),
            "fundamentals_generated_at": fundamentals.get("generated_at"),
            "fiscal_ai_news_generated_at": fiscal_ai_news.get("generated_at"),
        },
        "us_catalysts": collect_us_catalysts(fiscal_ai_news),
        "summary": {
            "focus": len([row for row in rows if row["decision"] == "FOCUS"]),
            "watch": len([row for row in rows if row["decision"] == "WATCH"]),
            "block": len([row for row in rows if row["decision"] == "BLOCK"]),
            "pass": len([row for row in rows if row["decision"] == "PASS"]),
        },
        "rows": rows,
        "note": "FOCUS/WATCH are research queue states, not direct trading instructions.",
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build consolidated candidate board.")
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--pullback-path", default=str(DEFAULT_PULLBACK))
    parser.add_argument("--preopen-filtered-path", default=str(DEFAULT_PREOPEN))
    parser.add_argument("--fundamentals-path", default=str(DEFAULT_FUNDAMENTALS))
    parser.add_argument("--fiscal-ai-news-path", default=str(DEFAULT_FISCAL_AI_NEWS))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        board = run(args)
        write_json(Path(args.output_path), board)
        print(f"wrote {args.output_path}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
