from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import read_json, read_text
from .status import normalize_pick_status


def parse_index_rows(index_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    text = read_text(index_path)
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line:
            continue
        columns = [col.strip().strip("`") for col in line.strip().strip("|").split("|")]
        if len(columns) < 4 or not re.fullmatch(r"\d{6}", columns[1]):
            continue
        status = normalize_pick_status(columns[8] if len(columns) > 8 else "")
        rows.append({
            "date": columns[0],
            "ticker": columns[1],
            "name": columns[2],
            "status": status,
        })
    return rows


def ticker_names_from_index(index_path: Path) -> dict[str, str]:
    return {row["ticker"]: row["name"] for row in parse_index_rows(index_path)}


def find_items_for_ticker(data: Any, ticker: str, limit: int = 5) -> list[Any]:
    matches: list[Any] = []

    def visit(value: Any) -> None:
        if len(matches) >= limit:
            return
        if isinstance(value, dict):
            values = {str(v) for v in value.values() if isinstance(v, (str, int))}
            if ticker in values or value.get("ticker") == ticker or value.get("code") == ticker:
                matches.append(value)
                return
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(data)
    return matches


def read_cache_matches(cache_dir: Path, ticker: str, filenames: list[str], limit_per_file: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for filename in filenames:
        path = cache_dir / filename
        data = read_json(path, default=None)
        if data is None:
            continue
        matches = find_items_for_ticker(data, ticker, limit=limit_per_file)
        if matches:
            results.append({
                "file": str(path),
                "matches": matches,
            })
    return results
