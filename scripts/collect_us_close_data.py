#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Collect US close signals and map them into Korea preopen candidates.

Outputs:
  picks/cache/us_close_snapshot.json
  picks/cache/preopen_candidates.json
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_US_SNAPSHOT = ROOT / "picks" / "cache" / "us_close_snapshot.json"
DEFAULT_CANDIDATES = ROOT / "picks" / "cache" / "preopen_candidates.json"
KST = timezone(timedelta(hours=9))
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"

SYMBOL_GROUPS = {
    "indices": {
        "^GSPC": "S&P 500",
        "^IXIC": "Nasdaq Composite",
        "^RUT": "Russell 2000",
        "^VIX": "VIX",
    },
    "sector_etfs": {
        "SMH": "VanEck Semiconductor ETF",
        "SOXX": "iShares Semiconductor ETF",
        "XLK": "Technology Select Sector SPDR",
        "XLE": "Energy Select Sector SPDR",
        "XLF": "Financial Select Sector SPDR",
        "XLI": "Industrial Select Sector SPDR",
        "XBI": "SPDR Biotech ETF",
    },
    "leaders": {
        "NVDA": "Nvidia",
        "AMD": "AMD",
        "MU": "Micron",
        "AVGO": "Broadcom",
        "TSLA": "Tesla",
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "AMZN": "Amazon",
        "GOOGL": "Alphabet",
        "LLY": "Eli Lilly",
    },
    "macro": {
        "^TNX": "US 10Y Yield",
        "DX-Y.NYB": "US Dollar Index",
        "CL=F": "WTI Crude Oil",
        "HG=F": "Copper",
        "GC=F": "Gold",
    },
}

KOREA_MAPPING = [
    {
        "signal_symbols": ["NVDA", "SMH", "SOXX"],
        "sector": "HBM/AI semiconductor",
        "candidates": [
            {"ticker": "000660", "name": "SK하이닉스"},
            {"ticker": "005930", "name": "삼성전자"},
            {"ticker": "042700", "name": "한미반도체"},
        ],
        "entry_condition": "시초가 갭 +3% 이하, 외국인 순매수 확인",
        "stop_condition": "진입가 대비 -5~-7% 또는 전일 저점 이탈",
    },
    {
        "signal_symbols": ["MU", "SMH", "SOXX"],
        "sector": "memory equipment",
        "candidates": [
            {"ticker": "240810", "name": "원익IPS"},
            {"ticker": "319660", "name": "피에스케이"},
        ],
        "entry_condition": "시초가 갭 +3% 이하, 외국인/기관 동반 매수 확인",
        "stop_condition": "진입가 대비 -7%",
    },
    {
        "signal_symbols": ["AVGO", "SMH", "SOXX"],
        "sector": "AI network PCB",
        "candidates": [
            {"ticker": "007660", "name": "이수페타시스"},
            {"ticker": "353200", "name": "대덕전자"},
            {"ticker": "222800", "name": "심텍"},
        ],
        "entry_condition": "시초가 갭 +3% 이하, 거래대금 증가 확인",
        "stop_condition": "진입가 대비 -8%",
    },
    {
        "signal_symbols": ["TSLA"],
        "sector": "EV/battery",
        "candidates": [
            {"ticker": "373220", "name": "LG에너지솔루션"},
            {"ticker": "006400", "name": "삼성SDI"},
            {"ticker": "066970", "name": "엘앤에프"},
        ],
        "entry_condition": "EV 섹터 동반 강세, 갭 +3% 이하",
        "stop_condition": "진입가 대비 -7%",
    },
    {
        "signal_symbols": ["AAPL"],
        "sector": "Apple supply chain",
        "candidates": [
            {"ticker": "011070", "name": "LG이노텍"},
            {"ticker": "009150", "name": "삼성전기"},
            {"ticker": "090460", "name": "비에이치"},
        ],
        "entry_condition": "Apple 공급망 뉴스 확인, 갭 +3% 이하",
        "stop_condition": "진입가 대비 -7%",
    },
    {
        "signal_symbols": ["XBI", "LLY"],
        "sector": "bio/CMO",
        "candidates": [
            {"ticker": "207940", "name": "삼성바이오로직스"},
            {"ticker": "068270", "name": "셀트리온"},
            {"ticker": "196170", "name": "알테오젠"},
        ],
        "entry_condition": "XBI/대형 바이오 동반 강세, 공시 리스크 없음",
        "stop_condition": "진입가 대비 -6%",
    },
    {
        "signal_symbols": ["XLI", "CL=F", "HG=F"],
        "sector": "power/infrastructure",
        "candidates": [
            {"ticker": "267260", "name": "HD현대일렉트릭"},
            {"ticker": "010120", "name": "LS ELECTRIC"},
            {"ticker": "066570", "name": "LG전자"},
        ],
        "entry_condition": "전력/원자재 신호 확인, 섹터 노출 한도 확인",
        "stop_condition": "진입가 대비 -7%",
    },
]

OFFLINE_QUOTES = {
    "^GSPC": 1.1,
    "^IXIC": 1.6,
    "^RUT": 0.4,
    "^VIX": -4.0,
    "SMH": 2.4,
    "SOXX": 2.1,
    "XLK": 1.3,
    "XLE": -0.8,
    "XLF": 0.2,
    "XLI": 0.6,
    "XBI": 0.1,
    "NVDA": 3.5,
    "AMD": -0.4,
    "MU": 4.8,
    "AVGO": 2.6,
    "TSLA": -1.2,
    "AAPL": 0.4,
    "MSFT": 1.2,
    "AMZN": 0.8,
    "GOOGL": 0.5,
    "LLY": 0.2,
    "^TNX": -1.0,
    "DX-Y.NYB": -0.2,
    "CL=F": -1.5,
    "HG=F": 1.1,
    "GC=F": -0.4,
}


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def flatten_symbols() -> Dict[str, Dict[str, str]]:
    """Return symbol metadata keyed by ticker."""
    symbols: Dict[str, Dict[str, str]] = {}
    for group, entries in SYMBOL_GROUPS.items():
        for symbol, name in entries.items():
            symbols[symbol] = {"symbol": symbol, "name": name, "group": group}
    return symbols


def fetch_yahoo_quote(symbol: str, timeout: int) -> Dict[str, Any]:
    """Fetch one daily quote from Yahoo chart JSON."""
    encoded = urllib.parse.quote(symbol, safe="")
    url = YAHOO_CHART_URL.format(symbol=encoded)
    req = urllib.request.Request(url, headers={"User-Agent": "stock-orchestrator/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result", [None])[0]
    if not result:
        raise RuntimeError("empty_yahoo_result")
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice")
    previous_close = meta.get("previousClose") or meta.get("chartPreviousClose")
    if price is None or previous_close in (None, 0):
        raise RuntimeError("missing_price")
    change_pct = ((float(price) - float(previous_close)) / float(previous_close)) * 100
    return {
        "symbol": symbol,
        "price": round(float(price), 4),
        "previous_close": round(float(previous_close), 4),
        "change_pct": round(change_pct, 4),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "regular_market_time": meta.get("regularMarketTime"),
        "ok": True,
        "source": "yahoo_chart",
    }


def offline_quote(symbol: str) -> Dict[str, Any]:
    """Return deterministic offline quote data."""
    change_pct = OFFLINE_QUOTES.get(symbol, 0.0)
    previous = 100.0
    price = previous * (1 + change_pct / 100)
    return {
        "symbol": symbol,
        "price": round(price, 4),
        "previous_close": previous,
        "change_pct": round(change_pct, 4),
        "currency": "USD",
        "exchange": "offline",
        "regular_market_time": None,
        "ok": True,
        "source": "offline_fixture",
    }


def collect_quotes(args: argparse.Namespace) -> List[Dict[str, Any]]:
    """Collect all configured US signals."""
    symbols = flatten_symbols()
    quotes: List[Dict[str, Any]] = []
    for symbol, metadata in symbols.items():
        try:
            quote = offline_quote(symbol) if args.offline_sample else fetch_yahoo_quote(symbol, args.timeout)
            quote.update(metadata)
        except Exception as exc:
            quote = {**metadata, "ok": False, "source": "yahoo_chart", "error": exc.__class__.__name__}
        quotes.append(quote)
    return quotes


def score_mapping(mapping: Dict[str, Any], quote_by_symbol: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Score one Korea mapping from US signal changes."""
    score = 0
    drivers: List[str] = []
    for symbol in mapping["signal_symbols"]:
        quote = quote_by_symbol.get(symbol, {})
        change = quote.get("change_pct")
        if change is None or not quote.get("ok"):
            continue
        threshold = 1.5 if quote.get("group") == "sector_etfs" else 3.0
        if float(change) >= threshold:
            score += 2
            drivers.append(f"{symbol} {change:+.2f}%")
        elif float(change) <= -threshold:
            score -= 1
            drivers.append(f"{symbol} {change:+.2f}%")
    return {"mapping": mapping, "score": score, "drivers": drivers}


def build_candidates(quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build Korea preopen candidates from US close quotes."""
    quote_by_symbol = {quote["symbol"]: quote for quote in quotes}
    scored = [score_mapping(mapping, quote_by_symbol) for mapping in KOREA_MAPPING]
    scored.sort(key=lambda item: item["score"], reverse=True)

    candidates: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    used_tickers = set()
    for item in scored:
        mapping = item["mapping"]
        decision = "WATCH" if item["score"] >= 2 else "PASS"
        for candidate in mapping["candidates"]:
            ticker = candidate["ticker"]
            if ticker in used_tickers:
                continue
            used_tickers.add(ticker)
            row = {
                "ticker": ticker,
                "name": candidate["name"],
                "sector": mapping["sector"],
                "score": item["score"],
                "decision": decision,
                "drivers": item["drivers"],
                "entry_condition": mapping["entry_condition"],
                "stop_condition": mapping["stop_condition"],
            }
            if decision == "WATCH" and len(candidates) < 3:
                candidates.append(row)
            elif decision == "PASS":
                blocked.append(row)
            break

    regime = "Risk-On"
    vix = quote_by_symbol.get("^VIX", {}).get("change_pct")
    nasdaq = quote_by_symbol.get("^IXIC", {}).get("change_pct")
    if vix is not None and float(vix) > 5:
        regime = "Risk-Off"
    elif nasdaq is not None and float(nasdaq) < -1:
        regime = "Neutral"

    return {
        "generated_at": now_kst(),
        "source": "us_close_snapshot",
        "market_regime_hint": regime,
        "preopen_candidates": candidates,
        "pass_candidates": blocked[:10],
        "hard_blocks": ["Gap +5% 이상 시 장전 추격 금지", "Capital Protection Gate 통과 전 신규 픽 저장 금지"],
        "confidence": "중간",
    }


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect US close signals for Korea preopen candidates.")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_US_SNAPSHOT))
    parser.add_argument("--candidates-path", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--timeout", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    quotes = collect_quotes(args)
    snapshot = {
        "generated_at": now_kst(),
        "market": "US",
        "mode": "offline_sample" if args.offline_sample else "live",
        "source": "offline_fixture" if args.offline_sample else "yahoo_chart",
        "groups": SYMBOL_GROUPS,
        "quotes": quotes,
    }
    candidates = build_candidates(quotes)
    candidates["mode"] = snapshot["mode"]
    candidates["quote_source"] = snapshot["source"]

    write_json(Path(args.snapshot_path), snapshot)
    write_json(Path(args.candidates_path), candidates)
    print(f"wrote {args.snapshot_path}")
    print(f"wrote {args.candidates_path}")

    failed = [quote["symbol"] for quote in quotes if not quote.get("ok")]
    if failed and not args.offline_sample:
        print(f"WARN missing US signals: {', '.join(failed)}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
