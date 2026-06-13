from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.io import read_text, write_json
from lib.universe import parse_index_rows, read_cache_matches

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "picks" / "cache"
INDEX_PATH = ROOT / "picks" / "INDEX.md"

PURPOSE_FILES = {
    "market": [
        "market_data_snapshot.json",
        "market_radar.json",
        "candidate_board.json",
        "pullback_candidates.json",
        "preopen_filtered_candidates.json",
    ],
    "flow": [
        "flow_snapshot.json",
        "foreign_rank_snapshot.json",
        "foreign_streak_candidates.json",
        "flow_streak_candidates.json",
        "flow_volume_candidates.json",
        "flow_comparison_latest.json",
    ],
    "risk": [
        "fundamentals_snapshot.json",
        "market_data_snapshot.json",
        "candidate_board.json",
        "market_radar.json",
        "fiscal_ai_investment_news.json",
    ],
}
PURPOSE_FILES["all"] = sorted({name for names in PURPOSE_FILES.values() for name in names})

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def compact_text(text: str, max_chars: int) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines() if line.strip())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def compact_value(value: Any, depth: int = 0) -> Any:
    if depth >= 3:
        if isinstance(value, dict):
            return {"_truncated": f"{len(value)} keys"}
        if isinstance(value, list):
            return [f"...{len(value)} items"]
        return value
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for index, (key, child) in enumerate(value.items()):
            if index >= 18:
                compacted["_truncated_keys"] = len(value) - index
                break
            if key in {"raw", "raw_basic_keys", "history", "sources"}:
                compacted[key] = "[omitted]"
                continue
            compacted[key] = compact_value(child, depth + 1)
        return compacted
    if isinstance(value, list):
        return [compact_value(child, depth + 1) for child in value[:5]]
    if isinstance(value, str) and len(value) > 300:
        return value[:300].rstrip() + "...[truncated]"
    return value


def pick_file_summary(ticker: str, max_chars: int) -> dict[str, Any] | None:
    candidates = sorted((ROOT / "picks").glob(f"20*_{ticker}.md"), reverse=True)
    if not candidates:
        return None
    path = candidates[0]
    return {
        "file": str(path),
        "excerpt": compact_text(read_text(path), max_chars),
    }


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    rows = parse_index_rows(INDEX_PATH)
    index_matches = [row for row in rows if row["ticker"] == args.ticker]
    files = PURPOSE_FILES[args.purpose]
    cache_matches = read_cache_matches(CACHE_DIR, args.ticker, files, limit_per_file=args.max_items)
    compact_cache_matches = [
        {
            "file": match["file"],
            "matches": [compact_value(item) for item in match["matches"]],
        }
        for match in cache_matches
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ticker": args.ticker,
        "purpose": args.purpose,
        "index_rows": index_matches,
        "pick_file": pick_file_summary(args.ticker, args.max_chars),
        "cache_matches": compact_cache_matches,
        "token_control": {
            "source_policy": "Projection only; avoid pasting full cache/news/DART payloads into agent prompts.",
            "max_items_per_cache": args.max_items,
            "pick_excerpt_max_chars": args.max_chars,
        },
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize ticker context without loading full cache files.")
    parser.add_argument("--ticker", required=True, help="Six digit stock ticker.")
    parser.add_argument("--purpose", choices=sorted(PURPOSE_FILES), default="all")
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--max-chars", type=int, default=3000)
    parser.add_argument("--output-path", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_summary(args)
    if args.output_path:
        write_json(Path(args.output_path), summary)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
