#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long,too-many-locals,too-many-branches
"""
Collect Korean stock operating data from Naver Finance and optional Toss Securities.

Outputs:
  picks/cache/market_data_snapshot.json
  picks/paper_price_snapshot.json when --update-paper-price-snapshot is supplied
"""

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from lib.universe import parse_index_rows


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_PAPER_PRICES = ROOT / "picks" / "paper_price_snapshot.json"
DEFAULT_INDEX = ROOT / "picks" / "INDEX.md"
DEFAULT_RULES = ROOT / "picks" / "paper_trading_rules.json"
DEFAULT_PREOPEN_CANDIDATES = ROOT / "picks" / "cache" / "preopen_candidates.json"
KST = timezone(timedelta(hours=9))
THEME_BLOCKLIST = {"naver", "정보", "증권", "종목", "투자", "페이지", "로그인"}


NAVER_BASIC_URL = "https://m.stock.naver.com/api/stock/{ticker}/basic"
NAVER_INTEGRATION_URL = "https://m.stock.naver.com/api/stock/{ticker}/integration"
NAVER_ITEM_URL = "https://finance.naver.com/item/main.naver?code={ticker}"
NAVER_DAILY_URL = "https://finance.naver.com/item/sise_day.naver?code={ticker}&page={page}"
TOSS_PUBLIC_URLS = (
    "https://tossinvest.com/stocks/{ticker}",
    "https://tossinvest.com/securities/stocks/{ticker}",
)


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 stock-orchestrator/1.0"
)


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")


def request_text(url: str, timeout: int = 10, headers: Optional[Dict[str, str]] = None) -> str:
    """Fetch a URL as text."""
    request_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
        "Referer": "https://finance.naver.com/",
    }
    if headers:
        request_headers.update(headers)
    req = Request(url, headers=request_headers)
    with urlopen(req, timeout=timeout) as res:  # nosec B310 - intended crawler input.
        raw = res.read()
        encoding = res.headers.get_content_charset() or "utf-8"
        return raw.decode(encoding, errors="replace")


def request_json(url: str, timeout: int = 10, headers: Optional[Dict[str, str]] = None) -> Any:
    """Fetch a URL and decode JSON."""
    return json.loads(request_text(url, timeout=timeout, headers=headers))


def clean_number(value: Any) -> Optional[float]:
    """Convert Korean finance number strings to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"N/A", "-", "null"}:
        return None
    text = text.replace(",", "").replace("%", "").replace("+", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {"-", "."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first_value(data: Any, keys: Iterable[str]) -> Any:
    """Find the first matching key recursively in nested JSON."""
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key] not in (None, ""):
                return data[key]
        for value in data.values():
            found = first_value(value, keys)
            if found not in (None, ""):
                return found
    elif isinstance(data, list):
        for value in data:
            found = first_value(value, keys)
            if found not in (None, ""):
                return found
    return None


def first_list(data: Any, keys: Iterable[str]) -> List[Any]:
    """Find the first list value matching one of the keys recursively."""
    if isinstance(data, dict):
        for key in keys:
            if isinstance(data.get(key), list):
                return data[key]
        for value in data.values():
            found = first_list(value, keys)
            if found:
                return found
    elif isinstance(data, list):
        for value in data:
            found = first_list(value, keys)
            if found:
                return found
    return []


def as_int(value: Any) -> Optional[int]:
    """Convert a number-like value to int."""
    number = clean_number(value)
    if number is None:
        return None
    return int(number)


def as_float(value: Any) -> Optional[float]:
    """Convert a number-like value to float."""
    number = clean_number(value)
    if number is None:
        return None
    return round(float(number), 4)


def average(values: List[float]) -> Optional[float]:
    """Return rounded average for a non-empty list."""
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def calculate_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    """Calculate RSI from newest-first closes."""
    chronological = list(reversed(closes))
    if len(chronological) <= period:
        return None
    deltas = [chronological[index] - chronological[index - 1] for index in range(1, len(chronological))]
    recent = deltas[-period:]
    gains = [delta for delta in recent if delta > 0]
    losses = [-delta for delta in recent if delta < 0]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 4)


def parse_tickers_from_index(path: Path) -> Dict[str, str]:
    """Read tracked ticker/name pairs from picks/INDEX.md."""
    rows = parse_index_rows(path)
    return {
        row["ticker"]: row["name"]
        for row in rows
        if not row["status"].startswith(("closed", "completed"))
    }


def parse_tickers_from_rules(path: Path) -> Dict[str, str]:
    """Read ticker/name pairs from paper trading rules."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    tickers: Dict[str, str] = {}
    for item in data.get("positions", []):
        ticker = str(item.get("ticker", "")).strip()
        if re.match(r"^\d{6}$", ticker):
            tickers[ticker] = str(item.get("name", ticker))
    return tickers


def parse_tickers_from_preopen_candidates(path: Path) -> Dict[str, str]:
    """Read ticker/name pairs from preopen candidate cache."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    tickers: Dict[str, str] = {}
    for section in ("preopen_candidates", "pass_candidates", "final_candidates", "passed", "blocked"):
        for item in data.get(section, []) or []:
            ticker = str(item.get("ticker", "")).strip().zfill(6)
            if re.match(r"^\d{6}$", ticker):
                tickers[ticker] = str(item.get("name") or ticker)
    return tickers


def resolve_tickers(args: argparse.Namespace) -> Dict[str, str]:
    """Resolve collection universe from CLI or project files."""
    tickers: Dict[str, str] = {}
    if args.tickers:
        for ticker in args.tickers.split(","):
            ticker = ticker.strip()
            if ticker:
                tickers[ticker] = ticker
    else:
        tickers.update(parse_tickers_from_index(Path(args.index_path)))
        tickers.update(parse_tickers_from_rules(Path(args.rules_path)))
        tickers.update(parse_tickers_from_preopen_candidates(Path(args.preopen_candidates_path)))
    return {ticker.zfill(6): name for ticker, name in tickers.items()}


def compact_error(exc: Exception) -> str:
    """Return a short transport error string."""
    if isinstance(exc, HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, URLError):
        return f"url_error:{exc.reason}"
    return exc.__class__.__name__


def parse_html_metadata(text: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Extract sector/industry/theme hints from a Naver item page."""
    cleaned = re.sub(r"\s+", " ", html.unescape(text))
    industry = None
    sector = None
    themes: List[str] = []

    industry_match = re.search(r"업종(?:명)?\s*</?[^>]*>\s*([^<|]{2,30})", cleaned)
    if industry_match:
        industry = industry_match.group(1).strip()

    sector_match = re.search(r"(?:KOSPI|KOSDAQ)\s*/\s*([^<|]{2,30})", cleaned)
    if sector_match:
        sector = sector_match.group(1).strip()

    for match in re.finditer(r"(?:테마|theme)[^가-힣A-Za-z0-9]{0,20}([가-힣A-Za-z0-9 /&+\-]{2,30})", cleaned, re.IGNORECASE):
        theme = match.group(1).strip(" -|")
        if theme and theme.lower() not in THEME_BLOCKLIST and theme not in themes:
            themes.append(theme)
        if len(themes) >= 5:
            break

    return sector, industry, themes


def parse_daily_rows(text: str) -> List[Dict[str, Any]]:
    """Parse Naver daily price rows from the quote table."""
    rows: List[Dict[str, Any]] = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 7:
            continue
        cleaned = [re.sub(r"<[^>]+>", "", html.unescape(cell)).strip() for cell in cells]
        if not re.match(r"^\d{4}\.\d{2}\.\d{2}$", cleaned[0]):
            continue
        close = as_int(cleaned[1])
        volume = as_int(cleaned[6])
        if close is None:
            continue
        rows.append({
            "date": cleaned[0],
            "close": close,
            "volume": volume,
        })
    return rows


def technical_from_history(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate technical indicators from newest-first daily rows."""
    closes = [float(row["close"]) for row in rows if row.get("close") is not None]
    volumes = [float(row["volume"]) for row in rows if row.get("volume") is not None]
    technical = {
        "history_days": len(closes),
        "ma5": average(closes[:5]),
        "ma20": average(closes[:20]),
        "ma60": average(closes[:60]),
        "ma120": average(closes[:120]),
        "rsi14": calculate_rsi(closes, 14),
        "volume_avg20": average(volumes[:20]),
    }
    return {key: value for key, value in technical.items() if value is not None}


def collect_naver_history(ticker: str, timeout: int, pages: int) -> Dict[str, Any]:
    """Collect best-effort daily history from Naver Finance and calculate indicators."""
    result: Dict[str, Any] = {
        "source": "naver_daily",
        "ticker": ticker,
        "ok": False,
        "errors": [],
    }
    if pages <= 0:
        result["status"] = "disabled"
        return result

    rows: List[Dict[str, Any]] = []
    for page in range(1, pages + 1):
        try:
            text = request_text(NAVER_DAILY_URL.format(ticker=quote(ticker), page=page), timeout=timeout)
            rows.extend(parse_daily_rows(text))
        except Exception as exc:
            result["errors"].append(f"page_{page}:{compact_error(exc)}")
            break

    seen = set()
    unique_rows = []
    for row in rows:
        if row["date"] in seen:
            continue
        seen.add(row["date"])
        unique_rows.append(row)

    result["history_count"] = len(unique_rows)
    if unique_rows:
        result["latest_date"] = unique_rows[0].get("date")
        result["latest_close"] = unique_rows[0].get("close")
        result["latest_volume"] = unique_rows[0].get("volume")
    result["technical"] = technical_from_history(unique_rows)
    result["ok"] = bool(result["technical"].get("ma20") or result["technical"].get("rsi14"))
    return result


def collect_naver(ticker: str, timeout: int, history_pages: int) -> Dict[str, Any]:
    """Collect quote and metadata from Naver Finance endpoints."""
    result: Dict[str, Any] = {
        "source": "naver",
        "ticker": ticker,
        "ok": False,
        "errors": [],
    }

    try:
        basic = request_json(NAVER_BASIC_URL.format(ticker=quote(ticker)), timeout=timeout)
        result.update({
            "name": first_value(basic, ("stockName", "name", "itemName", "korName")),
            "price": as_int(first_value(basic, ("closePrice", "nowVal", "currentPrice", "price"))),
            "change": as_int(first_value(basic, ("compareToPreviousClosePrice", "changePrice", "change"))),
            "change_rate": as_float(first_value(basic, ("fluctuationsRatio", "changeRate", "rate"))),
            "volume": as_int(first_value(basic, ("accumulatedTradingVolume", "volume", "tradingVolume"))),
            "trading_value": as_int(first_value(basic, ("accumulatedTradingValue", "transactionPrice", "tradingValue"))),
            "market_cap": as_int(first_value(basic, ("marketValue", "marketCap", "marketSum"))),
            "exchange": first_value(basic, ("stockExchangeType", "marketType", "exchange")),
            "raw_basic_keys": sorted(basic.keys()) if isinstance(basic, dict) else [],
        })
        result["ok"] = result.get("price") is not None
    except Exception as exc:
        result["errors"].append(f"basic:{compact_error(exc)}")

    try:
        integration = request_json(NAVER_INTEGRATION_URL.format(ticker=quote(ticker)), timeout=timeout)
        result["sector"] = first_value(integration, ("sectorName", "sector", "industryCodeName"))
        result["industry"] = first_value(integration, ("industryName", "industry", "bizType"))
        themes = []
        for item in first_list(integration, ("themeList", "themes", "themeInfos")):
            theme = first_value(item, ("name", "themeName", "title")) if isinstance(item, dict) else item
            if theme and str(theme) not in themes:
                themes.append(str(theme))
        if themes:
            result["themes"] = themes[:8]
    except Exception as exc:
        result["errors"].append(f"integration:{compact_error(exc)}")

    if not result.get("sector") and not result.get("industry") and not result.get("themes"):
        try:
            text = request_text(NAVER_ITEM_URL.format(ticker=quote(ticker)), timeout=timeout)
            sector, industry, themes = parse_html_metadata(text)
            if sector:
                result["sector"] = sector
            if industry:
                result["industry"] = industry
            if themes:
                result["themes"] = themes
        except Exception as exc:
            result["errors"].append(f"html:{compact_error(exc)}")

    history = collect_naver_history(ticker, timeout, history_pages)
    result["history"] = history
    if history.get("technical"):
        result["technical"] = history["technical"]
    if result.get("volume") is None and history.get("latest_volume") is not None:
        result["volume"] = history["latest_volume"]
        result["volume_source"] = "naver_daily_latest"

    return result


def collect_toss_public(ticker: str, timeout: int) -> Dict[str, Any]:
    """Best-effort public Toss Securities web crawl."""
    result: Dict[str, Any] = {
        "source": "toss_public",
        "ticker": ticker,
        "ok": False,
        "errors": [],
    }
    for template in TOSS_PUBLIC_URLS:
        url = template.format(ticker=quote(ticker))
        try:
            text = request_text(url, timeout=timeout, headers={"Referer": "https://tossinvest.com/"})
            result["url"] = url
            json_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text)
            if json_match:
                data = json.loads(html.unescape(json_match.group(1)))
                result.update({
                    "name": first_value(data, ("name", "stockName", "koreanName")),
                    "price": as_int(first_value(data, ("price", "closePrice", "currentPrice"))),
                    "change_rate": as_float(first_value(data, ("changeRate", "fluctuationsRatio"))),
                    "sector": first_value(data, ("sector", "sectorName")),
                    "industry": first_value(data, ("industry", "industryName")),
                })
                result["ok"] = result.get("price") is not None
                if result["ok"]:
                    return result
            result["errors"].append("no_public_quote_json")
        except Exception as exc:
            result["errors"].append(f"{template}:{compact_error(exc)}")
    return result


def collect_toss_official(ticker: str, timeout: int, endpoint_template: Optional[str]) -> Dict[str, Any]:
    """Collect Toss official Open API quote when credentials and endpoint are configured."""
    token = os.environ.get("TOSS_INVEST_TOKEN")
    account = os.environ.get("TOSS_INVEST_ACCOUNT")
    if not token or not endpoint_template:
        return {
            "source": "toss_official",
            "ticker": ticker,
            "ok": False,
            "status": "not_configured",
            "note": "Set TOSS_INVEST_TOKEN and TOSS_INVEST_QUOTE_URL_TEMPLATE after Toss Open API approval.",
        }

    headers = {"Authorization": f"Bearer {token}"}
    if account:
        headers["X-Tossinvest-Account"] = account
    url = endpoint_template.format(ticker=quote(ticker))
    try:
        data = request_json(url, timeout=timeout, headers=headers)
        return {
            "source": "toss_official",
            "ticker": ticker,
            "ok": True,
            "name": first_value(data, ("name", "stockName", "koreanName")),
            "price": as_int(first_value(data, ("price", "closePrice", "currentPrice", "lastPrice"))),
            "change": as_int(first_value(data, ("change", "changePrice"))),
            "change_rate": as_float(first_value(data, ("changeRate", "fluctuationsRatio"))),
            "volume": as_int(first_value(data, ("volume", "tradingVolume"))),
            "raw_keys": sorted(data.keys()) if isinstance(data, dict) else [],
        }
    except Exception as exc:
        return {
            "source": "toss_official",
            "ticker": ticker,
            "ok": False,
            "status": compact_error(exc),
        }


def offline_quote(ticker: str, name: str) -> Dict[str, Any]:
    """Return deterministic sample data for validation without network."""
    base = 50000 + int(ticker[-3:]) * 10
    volume = 100000 + int(ticker[-2:]) * 100
    return {
        "source": "offline_fixture",
        "ticker": ticker,
        "ok": True,
        "name": name,
        "price": base,
        "change": 100,
        "change_rate": 0.2,
        "volume": volume,
        "technical": {
            "history_days": 120,
            "ma5": round(base * 0.99, 4),
            "ma20": round(base * 0.96, 4),
            "ma60": round(base * 0.91, 4),
            "ma120": round(base * 0.86, 4),
            "rsi14": 54.0,
            "volume_avg20": volume * 2,
        },
        "sector": "fixture-sector",
        "industry": "fixture-industry",
        "themes": ["fixture-theme"],
    }


def merge_item(ticker: str, name: str, naver: Dict[str, Any], toss_official: Dict[str, Any], toss_public: Dict[str, Any]) -> Dict[str, Any]:
    """Build canonical item by preferring Naver, then Toss official, then Toss public."""
    candidates = [naver, toss_official, toss_public]
    price_source = next((item for item in candidates if item.get("ok") and item.get("price") is not None), {})
    meta_source = next((item for item in candidates if item.get("sector") or item.get("industry") or item.get("themes")), {})
    return {
        "ticker": ticker,
        "name": price_source.get("name") or name,
        "price": price_source.get("price"),
        "change": price_source.get("change"),
        "change_rate": price_source.get("change_rate"),
        "volume": price_source.get("volume"),
        "trading_value": price_source.get("trading_value"),
        "market_cap": price_source.get("market_cap"),
        "exchange": price_source.get("exchange"),
        "sector": meta_source.get("sector"),
        "industry": meta_source.get("industry"),
        "themes": meta_source.get("themes", []),
        "technical": price_source.get("technical") or meta_source.get("technical") or {},
        "primary_source": price_source.get("source"),
        "sources": {
            "naver": naver,
            "toss_official": toss_official,
            "toss_public": toss_public,
        },
    }


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def priced_count(snapshot: Dict[str, Any]) -> int:
    """Count items with a usable price."""
    return len([item for item in snapshot.get("items", []) if item.get("price") is not None])


def should_preserve_existing(args: argparse.Namespace, snapshot: Dict[str, Any], snapshot_path: Path) -> bool:
    """Avoid overwriting the operating snapshot with a mostly empty live crawl."""
    if args.offline_sample or args.allow_partial_write or not snapshot_path.exists():
        return False
    items = snapshot.get("items", [])
    if not items:
        return True
    missing_count = len([item for item in items if item.get("price") is None])
    return missing_count > 0 and priced_count(snapshot) == 0


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect all configured tickers."""
    tickers = resolve_tickers(args)
    if not tickers:
        raise RuntimeError("No tickers resolved. Pass --tickers or populate picks/INDEX.md.")

    items = []
    generated_at = now_kst()
    for ticker, name in tickers.items():
        if args.offline_sample:
            sample = offline_quote(ticker, name)
            naver = sample
            toss_official = {"source": "toss_official", "ticker": ticker, "ok": False, "status": "offline_sample"}
            toss_public = {"source": "toss_public", "ticker": ticker, "ok": False, "status": "offline_sample"}
        else:
            naver = collect_naver(ticker, args.timeout, args.history_pages)
            toss_official = collect_toss_official(ticker, args.timeout, args.toss_endpoint_template)
            toss_public = collect_toss_public(ticker, args.timeout) if args.include_toss_public else {"source": "toss_public", "ticker": ticker, "ok": False, "status": "disabled"}
            time.sleep(args.sleep_seconds)
        items.append(merge_item(ticker, name, naver, toss_official, toss_public))

    prices = {item["ticker"]: item["price"] for item in items if item.get("price") is not None}
    snapshot = {
        "generated_at": generated_at,
        "market": "KR",
        "mode": "offline_sample" if args.offline_sample else "live",
        "sources": {
            "naver": {
                "basic_url": NAVER_BASIC_URL,
                "integration_url": NAVER_INTEGRATION_URL,
                "item_url": NAVER_ITEM_URL,
                "daily_url": NAVER_DAILY_URL,
                "history_pages": args.history_pages,
            },
            "toss_official": {
                "base": "https://openapi.tossinvest.com/v1",
                "configured": bool(os.environ.get("TOSS_INVEST_TOKEN") and args.toss_endpoint_template),
            },
            "toss_public": {
                "enabled": bool(args.include_toss_public),
                "urls": list(TOSS_PUBLIC_URLS),
            },
        },
        "items": items,
        "prices": prices,
    }
    return snapshot


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect Naver/Toss Korean stock operating data.")
    parser.add_argument("--tickers", help="Comma-separated ticker list. Defaults to INDEX.md + paper rules.")
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX))
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES))
    parser.add_argument("--preopen-candidates-path", default=str(DEFAULT_PREOPEN_CANDIDATES))
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--paper-price-path", default=str(DEFAULT_PAPER_PRICES))
    parser.add_argument("--update-paper-price-snapshot", action="store_true")
    parser.add_argument("--offline-sample", action="store_true", help="Use deterministic fixture data without network.")
    parser.add_argument("--include-toss-public", action="store_true", help="Best-effort crawl of public Toss web pages.")
    parser.add_argument("--toss-endpoint-template", default=os.environ.get("TOSS_INVEST_QUOTE_URL_TEMPLATE"))
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--history-pages", type=int, default=12, help="Naver daily pages to fetch for MA/RSI. Use 0 to disable.")
    parser.add_argument("--allow-partial-write", action="store_true", help="Write snapshot even when all live prices are missing.")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        snapshot = collect(args)
        snapshot_path = Path(args.snapshot_path)
        missing = [item["ticker"] for item in snapshot["items"] if item.get("price") is None]
        preserved = should_preserve_existing(args, snapshot, snapshot_path)
        if preserved:
            failed_path = snapshot_path.with_suffix(".failed.json")
            write_json(failed_path, snapshot)
            print(f"WARN preserving existing {snapshot_path}; wrote failed attempt to {failed_path}")
        else:
            write_json(snapshot_path, snapshot)
            print(f"wrote {snapshot_path}")

        if args.update_paper_price_snapshot and not preserved:
            paper = {
                "date": snapshot["generated_at"],
                "source": str(snapshot_path).replace("\\", "/"),
                "prices": snapshot["prices"],
            }
            write_json(Path(args.paper_price_path), paper)
            print(f"wrote {args.paper_price_path}")

        if missing:
            print(f"WARN missing prices: {', '.join(missing)}")
            return 2
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
