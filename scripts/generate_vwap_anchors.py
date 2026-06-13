#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VWAP Anchors Generator (가중평균가격 닻 생성기)
Loads recent prices from market_data_snapshot.json and Naver Polling API
to update the VWAP anchors for the next trading session.

Outputs:
- picks/cache/vwap_anchors.json
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_JSON = ROOT / "picks" / "cache" / "market_data_snapshot.json"
OUTPUT_JSON = ROOT / "picks" / "cache" / "vwap_anchors.json"
KST = timezone(timedelta(hours=9))

TARGETS_CFG = {
    "066570": {"name": "LG전자", "default_close": 225500},
    "046890": {"name": "서울반도체", "default_close": 13200},
    "010170": {"name": "대한광통신", "default_close": 17070},
    "GLW": {"name": "코닝(US)", "default_close": 176.55}
}


def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def fetch_naver_polling_price(ticker: str, timeout_seconds: float = 5.0) -> int:
    """Fetch a current price from Naver Polling API when live lookup is explicitly enabled."""
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker}"
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as res:
            raw = res.read().decode("utf-8", errors="ignore")
            data = json.loads(raw)
            datas = data.get("result", {}).get("areas", [{}])[0].get("datas", [{}])
            if datas:
                return int(datas[0].get("nv", 0))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
        print(f"WARN: Failed to fetch polling price for {ticker}: {exc}", file=sys.stderr)
    return 0


def load_snapshot_prices(path: Path) -> dict[str, dict[str, float | int]]:
    """Load prices and ma20 from market_data_snapshot.json."""
    prices: dict[str, dict[str, float | int]] = {}
    if not path.exists():
        return prices
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        for item in items:
            ticker = str(item.get("ticker", "")).zfill(6)
            price = item.get("price")
            ma20 = item.get("technical", {}).get("ma20")
            if price:
                prices[ticker] = {
                    "price": int(price),
                    "vwap_ma20": float(ma20) if ma20 else float(price)
                }
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"WARN: Failed to read market snapshot: {exc}", file=sys.stderr)
    return prices


def resolve_base_date(value: str) -> str:
    """Resolve base date from CLI value."""
    if value != "today":
        return value
    return datetime.now(KST).strftime("%Y-%m-%d")


def build_anchors(args: argparse.Namespace) -> dict[str, Any]:
    """Build VWAP anchors from snapshot, optional live lookup, and offline defaults."""
    base_date = resolve_base_date(args.base_date)
    snapshot_prices = load_snapshot_prices(Path(args.snapshot_path))
    anchors: dict[str, Any] = {}

    for ticker, cfg in TARGETS_CFG.items():
        price = 0
        vwap_ma20 = 0.0

        if ticker in snapshot_prices:
            price = int(snapshot_prices[ticker]["price"])
            vwap_ma20 = float(snapshot_prices[ticker]["vwap_ma20"])
            print(f"Loaded {cfg['name']} ({ticker}) from market snapshot")
        elif args.include_live_naver and ticker.isdigit():
            polled_price = fetch_naver_polling_price(ticker, args.timeout_seconds)
            if polled_price > 0:
                price = polled_price
                vwap_ma20 = float(polled_price)
                print(f"Polled {cfg['name']} ({ticker}) from Naver Polling API")

        if price == 0:
            price = cfg["default_close"]
            vwap_ma20 = float(cfg["default_close"])
            print(f"Using default close for {cfg['name']} ({ticker})")

        anchors[ticker] = {
            "name": cfg["name"],
            "ticker": ticker,
            "base_date": base_date,
            "close_baseline": price,
            "vwap_ma20": vwap_ma20,
            "formulas_documentation": {
                "undercut_and_spring_threshold": "Threshold = vwap_ma20 * 0.96 (Undercut by 4%)",
                "spring_recovery_trigger": "Price recoveries back above vwap_ma20 * 0.98"
            }
        }
        print(f"  - {cfg['name']} ({ticker}) -> Close: {price:,}, VWAP MA20: {vwap_ma20:,.1f}")

    return {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "base_date": base_date,
        "model_name": "VWAP Baseline Anchor Model",
        "source": "market_snapshot+optional_live_naver+defaults",
        "live_lookup_enabled": bool(args.include_live_naver),
        "tickers": anchors
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate VWAP anchor baselines.")
    parser.add_argument("--snapshot-path", default=str(SNAPSHOT_JSON))
    parser.add_argument("--output-path", default=str(OUTPUT_JSON))
    parser.add_argument("--base-date", default="today", help="YYYY-MM-DD or 'today'.")
    parser.add_argument("--include-live-naver", action="store_true", help="Fetch missing Korean prices from Naver.")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    print("=== [VWAP Anchors Generator] Updating anchors ===")

    output_data = build_anchors(args)

    try:
        output_path = Path(args.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write
        tmp_file = output_path.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_file.replace(output_path)
        print(f"\n[OK] Updated VWAP anchors (Base Date: {output_data['base_date']}) at: {output_path}")
        return 0
    except OSError as exc:
        print(f"ERROR: Failed to save VWAP anchors: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
