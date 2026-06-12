#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Prepare five-day foreign/institution flow snapshots and optionally merge available items.

Outputs:
  picks/cache/flow_snapshot.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from lib.io import read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MARKET = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_SNAPSHOT = ROOT / "picks" / "cache" / "flow_snapshot.json"
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")





def resolve_tickers(market: Dict[str, Any], tickers_arg: str) -> Dict[str, str]:
    """Resolve ticker/name pairs from CLI or market snapshot."""
    tickers: Dict[str, str] = {}
    if tickers_arg:
        for ticker in tickers_arg.split(","):
            ticker = ticker.strip().zfill(6)
            if ticker:
                tickers[ticker] = ticker
        return tickers
    for item in market.get("items", []):
        ticker = str(item.get("ticker", "")).zfill(6)
        if ticker.isdigit() and len(ticker) == 6:
            tickers[ticker] = str(item.get("name") or ticker)
    return tickers


def business_start(end: datetime, days: int) -> str:
    """Return a conservative KRX date window start."""
    return (end - timedelta(days=days * 2 + 3)).strftime("%Y%m%d")


def offline_flow(ticker: str, name: str) -> Dict[str, Any]:
    """Return deterministic flow fixture."""
    seed = int(ticker[-3:])
    foreign = (seed - 500) * 1000
    institution = (500 - seed // 2) * 800
    return {
        "ticker": ticker,
        "name": name,
        "ok": True,
        "source": "offline_fixture",
        "foreign_net_buy_5d": foreign,
        "institution_net_buy_5d": institution,
        "combined_net_buy_5d": foreign + institution,
    }


def disabled_flow(ticker: str, name: str) -> Dict[str, Any]:
    """Return an explicit disabled provider row without querying KRX."""
    return {
        "ticker": ticker,
        "name": name,
        "ok": False,
        "source": "disabled",
        "status": "provider_not_configured",
        "note": "KRX/pykrx flow querying is disabled because it returned empty responses in this environment.",
    }


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect flow for all resolved tickers."""
    market = read_json(Path(args.market_snapshot_path), default={})
    tickers = resolve_tickers(market, args.tickers)
    today = datetime.now(KST)
    end = args.date or today.strftime("%Y%m%d")
    start = args.start_date or business_start(today, 5)
    items = [offline_flow(ticker, name) if args.offline_sample else disabled_flow(ticker, name) for ticker, name in tickers.items()]
    return {
        "generated_at": now_kst(),
        "mode": "offline_sample" if args.offline_sample else "disabled",
        "source": "offline_fixture" if args.offline_sample else "disabled",
        "start_date": start,
        "end_date": end,
        "items": items,
        "note": "Live KRX/pykrx flow collection has been removed from the operating loop.",
    }


def merge_into_market(market_path: Path, flow: Dict[str, Any]) -> None:
    """Merge flow items into market snapshot items."""
    market = read_json(market_path, default={})
    flow_by_ticker = {str(item.get("ticker", "")).zfill(6): item for item in flow.get("items", []) if item.get("ok")}
    for item in market.get("items", []):
        ticker = str(item.get("ticker", "")).zfill(6)
        flow_item = flow_by_ticker.get(ticker)
        if not flow_item:
            continue
        item["flow"] = {
            "foreign_net_buy_5d": flow_item.get("foreign_net_buy_5d"),
            "institution_net_buy_5d": flow_item.get("institution_net_buy_5d"),
            "combined_net_buy_5d": flow_item.get("combined_net_buy_5d"),
            "source": flow_item.get("source"),
            "generated_at": flow.get("generated_at"),
        }
    market["flow_snapshot_generated_at"] = flow.get("generated_at")
    write_json(market_path, market)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect foreign/institution 5-day flow.")
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET))
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--tickers", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--update-market-snapshot", action="store_true")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        flow = collect(args)
        write_json(Path(args.snapshot_path), flow)
        print(f"wrote {args.snapshot_path}")
        if args.update_market_snapshot:
            merge_into_market(Path(args.market_snapshot_path), flow)
            print(f"updated {args.market_snapshot_path}")
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
