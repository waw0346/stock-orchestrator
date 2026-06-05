#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Collect foreign net-buy rank data from Kiwoom REST API.

Outputs:
  picks/cache/foreign_flow_history.csv
  picks/cache/foreign_rank_snapshot.json
"""

import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
DEFAULT_SNAPSHOT = ROOT / "picks" / "cache" / "foreign_rank_snapshot.json"
KST = timezone(timedelta(hours=9))
CSV_FIELDS = ["date", "ticker", "name", "foreign_net_buy", "institution_net_buy", "close", "volume"]
KIWOOM_RANK_ENDPOINT = "/api/dostk/rkinfo"
KIWOOM_TOKEN_ENDPOINT = "/oauth2/token"


def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> datetime:
    """Return current KST datetime."""
    return datetime.now(KST)


def clean_int(value: Any) -> int:
    """Parse Kiwoom signed numeric strings."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    if not text:
        return 0
    return sign * int(float(text))


def clean_abs_int(value: Any) -> int:
    """Parse a possibly signed price as an absolute integer."""
    return abs(clean_int(value))


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_existing_rows(path: Path) -> List[Dict[str, str]]:
    """Read an existing foreign flow CSV if present."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader if row.get("date") and row.get("ticker")]


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    """Write normalized foreign flow CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in CSV_FIELDS})


def merge_rows(existing: List[Dict[str, str]], fresh: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Replace same date/ticker rows with fresh rows and preserve older history."""
    fresh_keys = {(str(row["date"]), str(row["ticker"]).zfill(6)) for row in fresh}
    merged: List[Dict[str, Any]] = [
        row for row in existing
        if (str(row.get("date")), str(row.get("ticker", "")).zfill(6)) not in fresh_keys
    ]
    merged.extend(fresh)
    merged.sort(key=lambda row: (str(row.get("date")), str(row.get("ticker"))))
    return merged


def request_json(url: str, body: Dict[str, Any], headers: Dict[str, str], timeout: int) -> Dict[str, Any]:
    """POST a JSON request and decode the JSON response."""
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={**headers, "Content-Type": "application/json;charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - user-configured brokerage API.
        return json.loads(response.read().decode("utf-8"))


def get_token(args: argparse.Namespace) -> str:
    """Return a Kiwoom access token from env or by client credentials."""
    token = args.access_token or os.environ.get("KIWOOM_ACCESS_TOKEN")
    if token:
        return token
    app_key = args.app_key or os.environ.get("KIWOOM_APP_KEY")
    app_secret = args.app_secret or os.environ.get("KIWOOM_APP_SECRET")
    if not app_key or not app_secret:
        raise RuntimeError("Missing KIWOOM_ACCESS_TOKEN or KIWOOM_APP_KEY/KIWOOM_APP_SECRET")
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "secretkey": app_secret,
    }
    response = request_json(args.base_url.rstrip("/") + KIWOOM_TOKEN_ENDPOINT, body, {}, args.timeout)
    issued = response.get("token")
    if not issued:
        raise RuntimeError(f"Kiwoom token response missing token: {response.get('return_msg') or response}")
    return str(issued)


def normalize_rank_item(item: Dict[str, Any], date: str) -> Dict[str, Any]:
    """Normalize one ka10034 rank item to project CSV fields."""
    return {
        "date": date,
        "ticker": str(item.get("stk_cd", "")).strip().lstrip("A").zfill(6),
        "name": str(item.get("stk_nm") or "").strip(),
        "foreign_net_buy": clean_int(item.get("netprps_qty")),
        "institution_net_buy": 0,
        "close": clean_abs_int(item.get("cur_prc")),
        "volume": clean_abs_int(item.get("trde_qty")),
        "rank": clean_abs_int(item.get("rank")),
        "raw": item,
    }


def offline_items(days: int, top: int) -> List[Dict[str, Any]]:
    """Return deterministic Kiwoom-like foreign rank rows for tests."""
    base = now_kst().date()
    fixtures = [
        ("005930", "삼성전자", [12000000000, 15000000000, 18000000000], 331000, 1200000),
        ("402340", "SK스퀘어", [7000000000, 9000000000, 11000000000], 1251000, 80000),
        ("000660", "SK하이닉스", [8000000000, -1000000000, 9000000000], 2120000, 500000),
    ][:top]
    rows: List[Dict[str, Any]] = []
    for offset in range(days):
        day = (base - timedelta(days=days - offset - 1)).isoformat()
        for rank, (ticker, name, values, close, volume) in enumerate(fixtures, start=1):
            value = values[offset % len(values)]
            rows.append({
                "date": day,
                "ticker": ticker,
                "name": name,
                "foreign_net_buy": value,
                "institution_net_buy": 0,
                "close": close,
                "volume": volume,
                "rank": rank,
                "raw": {
                    "rank": str(rank),
                    "stk_cd": ticker,
                    "stk_nm": name,
                    "cur_prc": str(close),
                    "trde_qty": str(volume),
                    "netprps_qty": f"{value:+d}",
                },
            })
    return rows


def collect_live(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Collect foreign net-buy rank data from Kiwoom ka10034."""
    token = get_token(args)
    headers = {
        "authorization": f"Bearer {token}",
        "api-id": args.api_id,
    }
    body = {
        "mrkt_tp": args.market_type,
        "trde_tp": args.trade_type,
        "dt": args.period,
        "stex_tp": args.exchange_type,
    }
    url = args.base_url.rstrip("/") + KIWOOM_RANK_ENDPOINT
    response = request_json(url, body, headers, args.timeout)
    if int(response.get("return_code", 0)) != 0:
        raise RuntimeError(f"Kiwoom API error: {response.get('return_msg') or response}")
    items = response.get("for_dt_trde_upper") or response.get("items") or []
    date = args.date or now_kst().date().isoformat()
    return [normalize_rank_item(item, date) for item in items[:args.top]]


def build_snapshot(args: argparse.Namespace, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a JSON snapshot from normalized rows."""
    return {
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "provider": "kiwoom",
        "mode": "offline_sample" if args.offline_sample else "live",
        "api_id": args.api_id,
        "rank_endpoint": KIWOOM_RANK_ENDPOINT,
        "market_type": args.market_type,
        "trade_type": args.trade_type,
        "period": args.period,
        "exchange_type": args.exchange_type,
        "items": [
            {key: value for key, value in row.items() if key != "raw"}
            for row in rows
        ],
        "note": "foreign_net_buy is sourced from Kiwoom netprps_qty; institution_net_buy is 0 because ka10034 is foreign-period rank.",
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect Kiwoom foreign net-buy rank data.")
    parser.add_argument("--output-csv-path", default=str(DEFAULT_CSV))
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--append-existing", action="store_true", default=True)
    parser.add_argument("--date", default="")
    parser.add_argument("--days", type=int, default=1, help="Offline sample days. Live mode writes one collection date.")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--base-url", default=os.environ.get("KIWOOM_BASE_URL", "https://api.kiwoom.com"))
    parser.add_argument("--access-token", default="")
    parser.add_argument("--app-key", default="")
    parser.add_argument("--app-secret", default="")
    parser.add_argument("--api-id", default="ka10034")
    parser.add_argument("--market-type", default="000", help="000: all, 001: KOSPI, 101: KOSDAQ")
    parser.add_argument("--trade-type", default="2", help="1: net sell, 2: net buy, 3: net trade")
    parser.add_argument("--period", default="0", help="0: today, 1: previous day, 5/10/20/60: period")
    parser.add_argument("--exchange-type", default="1", help="1: KRX, 2: NXT, 3: integrated")
    parser.add_argument("--timeout", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        rows = offline_items(args.days, args.top) if args.offline_sample else collect_live(args)
        existing = read_existing_rows(Path(args.output_csv_path)) if args.append_existing else []
        merged = merge_rows(existing, rows)
        write_csv(Path(args.output_csv_path), merged)
        write_json(Path(args.snapshot_path), build_snapshot(args, rows))
        print(f"wrote {args.output_csv_path}")
        print(f"wrote {args.snapshot_path}")
        print(f"rows {len(rows)} / history {len(merged)}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
