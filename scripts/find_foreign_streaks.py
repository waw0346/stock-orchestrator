#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Find Korean stocks with consecutive foreign net-buy streaks from an end-of-day CSV.

Outputs:
  picks/cache/foreign_streak_candidates.json
"""

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "foreign_streak_candidates.json"
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def parse_int(value: Any) -> int:
    """Parse integers from CSV cells, allowing commas and blanks."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    return int(float(text))


def read_rows(path: Path) -> List[Dict[str, Any]]:
    """Read normalized CSV rows."""
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "ticker", "foreign_net_buy"}
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"input CSV missing columns: {', '.join(missing)}")
        for row in reader:
            ticker = str(row.get("ticker", "")).strip().zfill(6)
            date = str(row.get("date", "")).strip()
            if not ticker.isdigit() or len(ticker) != 6 or not date:
                continue
            rows.append({
                "date": date,
                "ticker": ticker,
                "name": str(row.get("name") or ticker).strip(),
                "foreign_net_buy": parse_int(row.get("foreign_net_buy")),
                "institution_net_buy": parse_int(row.get("institution_net_buy")),
                "close": parse_int(row.get("close")),
                "volume": parse_int(row.get("volume")),
            })
    return rows


def latest_streak(sorted_rows: List[Dict[str, Any]]) -> int:
    """Count consecutive positive foreign net-buy days ending at the latest row."""
    streak = 0
    for row in reversed(sorted_rows):
        if row["foreign_net_buy"] <= 0:
            break
        streak += 1
    return streak


def score_candidates(rows: List[Dict[str, Any]], min_consecutive_days: int, lookback_days: int, top: int) -> Dict[str, Any]:
    """Return ranked candidates passing the consecutive foreign-buy gate."""
    by_ticker: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_ticker[row["ticker"]].append(row)

    candidates: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    for ticker, ticker_rows in by_ticker.items():
        ticker_rows.sort(key=lambda item: item["date"])
        window = ticker_rows[-lookback_days:] if lookback_days > 0 else ticker_rows
        streak = latest_streak(window)
        foreign_sum = sum(row["foreign_net_buy"] for row in window)
        institution_sum = sum(row["institution_net_buy"] for row in window)
        positive_days = sum(1 for row in window if row["foreign_net_buy"] > 0)
        latest = window[-1]
        row = {
            "ticker": ticker,
            "name": latest["name"],
            "latest_date": latest["date"],
            "close": latest["close"],
            "consecutive_foreign_buy_days": streak,
            "foreign_positive_days": positive_days,
            "lookback_days": len(window),
            "foreign_net_buy_sum": foreign_sum,
            "institution_net_buy_sum": institution_sum,
            "latest_foreign_net_buy": latest["foreign_net_buy"],
            "latest_institution_net_buy": latest["institution_net_buy"],
            "latest_volume": latest["volume"],
        }
        if streak >= min_consecutive_days:
            candidates.append(row)
        else:
            row["reason"] = "foreign_streak_below_minimum"
            rejected.append(row)

    candidates.sort(
        key=lambda item: (
            item["foreign_net_buy_sum"],
            item["consecutive_foreign_buy_days"],
            item["institution_net_buy_sum"],
        ),
        reverse=True,
    )
    return {
        "generated_at": now_kst(),
        "mode": "csv",
        "source": "foreign_flow_history_csv",
        "input_rows": len(rows),
        "min_consecutive_days": min_consecutive_days,
        "lookback_days": lookback_days,
        "top": top,
        "candidates": candidates[:top],
        "rejected": rejected,
        "summary": {
            "candidate_count": min(len(candidates), top),
            "rejected_count": len(rejected),
            "universe_count": len(by_ticker),
        },
    }


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Find consecutive foreign net-buy streaks.")
    parser.add_argument("--input-csv-path", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--min-consecutive-days", type=int, default=3)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--top", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        rows = read_rows(Path(args.input_csv_path))
        result = score_candidates(rows, args.min_consecutive_days, args.lookback_days, args.top)
        write_json(Path(args.output_path), result)
        print(f"wrote {args.output_path}")
        print(f"candidates {result['summary']['candidate_count']} / universe {result['summary']['universe_count']}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
