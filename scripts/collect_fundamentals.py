#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Collect Korean stock fundamentals from OpenDART or pykrx.

Outputs:
  picks/cache/fundamentals_snapshot.json
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX = ROOT / "picks" / "INDEX.md"
DEFAULT_RULES = ROOT / "picks" / "paper_trading_rules.json"
DEFAULT_MARKET_SNAPSHOT = ROOT / "picks" / "cache" / "market_data_snapshot.json"
DEFAULT_PREOPEN_CANDIDATES = ROOT / "picks" / "cache" / "preopen_candidates.json"
DEFAULT_SNAPSHOT = ROOT / "picks" / "cache" / "fundamentals_snapshot.json"
DEFAULT_CORP_CACHE = ROOT / "picks" / "cache" / "opendart_corp_codes.json"
DEFAULT_ENV_FILE = ROOT / ".env.local"
KST = timezone(timedelta(hours=9))
FUNDAMENTAL_FIELDS = ("BPS", "PER", "PBR", "EPS", "DIV", "DPS")
OPENDART_BASE_URL = "https://opendart.fss.or.kr/api"
OPENDART_INDEX_CLASSES = ("M210000", "M220000", "M230000", "M240000")


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> datetime:
    """Return current KST datetime."""
    return datetime.now(KST)


def default_krx_date() -> str:
    """Return a KRX-friendly date string, moving weekends back to Friday."""
    day = now_kst()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.strftime("%Y%m%d")


def default_business_year() -> str:
    """Return the latest normally available annual report year."""
    return str(now_kst().year - 1)


def parse_tickers_from_index(path: Path) -> Dict[str, str]:
    """Read non-closed ticker/name pairs from picks/INDEX.md."""
    tickers: Dict[str, str] = {}
    if not path.exists():
        return tickers
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*20\d{2}-\d{2}-\d{2}\s*\|", line):
            continue
        columns = [column.strip() for column in line.split("|")]
        if len(columns) < 10:
            continue
        ticker = columns[2]
        name = columns[3]
        status = columns[9]
        if re.match(r"^\d{6}$", ticker) and not status.startswith(("closed", "completed")):
            tickers[ticker] = name
    return tickers


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


def parse_tickers_from_market_snapshot(path: Path) -> Dict[str, str]:
    """Read ticker/name pairs from market data snapshot."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    tickers: Dict[str, str] = {}
    for item in data.get("items", []) or []:
        ticker = str(item.get("ticker", "")).strip().zfill(6)
        if re.match(r"^\d{6}$", ticker):
            tickers[ticker] = str(item.get("name") or ticker)
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
                tickers[ticker.zfill(6)] = ticker.zfill(6)
    else:
        tickers.update(parse_tickers_from_index(Path(args.index_path)))
        tickers.update(parse_tickers_from_rules(Path(args.rules_path)))
        tickers.update(parse_tickers_from_market_snapshot(Path(args.market_snapshot_path)))
        tickers.update(parse_tickers_from_preopen_candidates(Path(args.preopen_candidates_path)))
    return {ticker.zfill(6): name for ticker, name in tickers.items()}


def clean_number(value: Any) -> Optional[float]:
    """Convert pykrx scalar values into JSON-friendly numbers."""
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
    except ValueError:
        pass
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "nan", "NaN", "None"}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number.is_integer():
        return int(number)
    return round(number, 6)


def parse_amount(value: Any) -> Optional[int]:
    """Convert OpenDART amount strings into integers."""
    number = clean_number(value)
    if number is None:
        return None
    return int(number)


def first_metric(indicators: Dict[str, Optional[float]], names: List[str]) -> Optional[float]:
    """Return the first available indicator from a list of Korean OpenDART names."""
    for name in names:
        value = indicators.get(name)
        if value is not None:
            return value
    return None


def read_env_file_value(path: Path, key: str) -> str:
    """Read a single KEY=value from a local env file without exporting it."""
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, value = text.split("=", 1)
        if name.strip() != key:
            continue
        value = value.strip().strip('"').strip("'")
        return value
    return ""


def offline_item(ticker: str, name: str, date: str) -> Dict[str, Any]:
    """Return deterministic sample fundamentals for tests."""
    seed = int(ticker[-3:])
    bps = 20000 + seed * 10
    eps = 1000 + seed
    per = round((50000 + seed * 10) / eps, 4)
    pbr = round((50000 + seed * 10) / bps, 4)
    return {
        "ticker": ticker,
        "name": name,
        "date": date,
        "bps": bps,
        "per": per,
        "pbr": pbr,
        "eps": eps,
        "div": round(1 + (seed % 20) / 10, 4),
        "dps": 500 + seed,
        "valuation_fields_available": True,
        "ok": True,
        "source": "offline_fixture",
    }


def opendart_request_json(endpoint: str, params: Dict[str, str], api_key: str) -> Dict[str, Any]:
    """Call an OpenDART JSON endpoint."""
    query = urllib.parse.urlencode({"crtfc_key": api_key, **params})
    url = f"{OPENDART_BASE_URL}/{endpoint}.json?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        text = response.read().decode("utf-8")
    return json.loads(text)


def load_opendart_corp_codes(api_key: str, cache_path: Path, refresh: bool = False) -> Dict[str, Dict[str, str]]:
    """Load OpenDART corp_code mapping keyed by 6-digit stock code."""
    if cache_path.exists() and not refresh:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return {str(item["stock_code"]).zfill(6): item for item in cached.get("items", [])}

    query = urllib.parse.urlencode({"crtfc_key": api_key})
    url = f"{OPENDART_BASE_URL}/corpCode.xml?{query}"
    with urllib.request.urlopen(url, timeout=60) as response:
        payload = response.read()

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        xml_name = archive.namelist()[0]
        root = ElementTree.fromstring(archive.read(xml_name))

    items: List[Dict[str, str]] = []
    for element in root.findall("list"):
        stock_code = (element.findtext("stock_code") or "").strip()
        if not re.match(r"^\d{6}$", stock_code):
            continue
        items.append({
            "corp_code": (element.findtext("corp_code") or "").strip(),
            "corp_name": (element.findtext("corp_name") or "").strip(),
            "stock_code": stock_code,
            "modify_date": (element.findtext("modify_date") or "").strip(),
        })

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "source": "opendart_corpCode",
        "items": items,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {item["stock_code"]: item for item in items}


def collect_opendart(args: argparse.Namespace, tickers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Collect financial statement metrics using OpenDART."""
    api_key = os.environ.get(args.opendart_api_key_env, "").strip()
    if not api_key:
        api_key = read_env_file_value(Path(args.env_file), args.opendart_api_key_env)
    if not api_key:
        raise RuntimeError(f"{args.opendart_api_key_env} is not set. Set it as an environment variable or in {args.env_file}.")

    corp_codes = load_opendart_corp_codes(api_key, Path(args.opendart_corp_cache), args.refresh_corp_codes)
    items: List[Dict[str, Any]] = []

    for ticker, name in tickers.items():
        corp = corp_codes.get(ticker)
        if corp is None:
            items.append({
                "ticker": ticker,
                "name": name,
                "date": args.date,
                "ok": False,
                "source": "opendart",
                "error": "ticker_missing_from_opendart_corp_codes",
            })
            continue

        indicator_rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        for index_class in OPENDART_INDEX_CLASSES:
            data = opendart_request_json("fnlttSinglIndx", {
                "corp_code": corp["corp_code"],
                "bsns_year": args.business_year,
                "reprt_code": args.report_code,
                "idx_cl_code": index_class,
            }, api_key)
            status = str(data.get("status", ""))
            if status == "000":
                indicator_rows.extend(data.get("list", []))
            elif status != "013":
                errors.append(f"{index_class}:{status}:{data.get('message', '')}")

        account_values: Dict[str, Optional[int]] = {}
        accounts_data = opendart_request_json("fnlttSinglAcnt", {
            "corp_code": corp["corp_code"],
            "bsns_year": args.business_year,
            "reprt_code": args.report_code,
        }, api_key)
        account_status = str(accounts_data.get("status", ""))
        if account_status == "000":
            for row in accounts_data.get("list", []):
                account_name = str(row.get("account_nm", "")).strip()
                if account_name in {"자산총계", "부채총계", "자본총계", "매출액", "영업이익", "당기순이익"}:
                    account_values[account_name] = parse_amount(row.get("thstrm_amount") or row.get("thstrm_add_amount"))
        elif account_status != "013":
            errors.append(f"accounts:{account_status}:{accounts_data.get('message', '')}")

        indicators = {
            str(row.get("idx_nm", "")).strip(): clean_number(row.get("idx_val"))
            for row in indicator_rows
            if str(row.get("idx_nm", "")).strip()
        }
        gate_metrics = {
            "roe": first_metric(indicators, ["ROE"]),
            "debt_ratio": first_metric(indicators, ["부채비율"]),
            "current_ratio": first_metric(indicators, ["유동비율"]),
            "operating_income_growth_yoy": first_metric(indicators, ["영업이익증가율(YoY)"]),
            "revenue_growth_yoy": first_metric(indicators, ["매출액증가율(YoY)"]),
            "net_income_margin": first_metric(indicators, ["순이익률"]),
        }
        ok = bool(indicators or account_values) and not errors
        item: Dict[str, Any] = {
            "ticker": ticker,
            "name": name,
            "date": args.date,
            "business_year": args.business_year,
            "report_code": args.report_code,
            "corp_code": corp["corp_code"],
            "corp_name": corp["corp_name"],
            "bps": None,
            "per": None,
            "pbr": None,
            "eps": None,
            "div": None,
            "dps": None,
            "valuation_fields_available": False,
            "ok": ok,
            "source": "opendart",
            "financial_indicators": indicators,
            "account_values": account_values,
            "gate_metrics": gate_metrics,
            "missing_fields": [field.lower() for field in FUNDAMENTAL_FIELDS],
            "note": "OpenDART provides disclosure financial indicators/accounts, not KRX daily valuation fields.",
        }
        if errors:
            item["errors"] = errors
        if not indicators and not account_values:
            item["error"] = "no_opendart_financial_data"
        items.append(item)
    return items


def collect_pykrx(args: argparse.Namespace, tickers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Collect fundamentals using pykrx."""
    try:
        from pykrx import stock  # type: ignore
    except ImportError as exc:
        raise RuntimeError("pykrx is not installed. Install with: python -m pip install pykrx pandas") from exc

    df = stock.get_market_fundamental_by_ticker(date=args.date, market=args.market)
    if df is None or getattr(df, "empty", True):
        raise RuntimeError(f"pykrx returned no fundamental data for date={args.date}, market={args.market}")
    missing_columns = [field for field in FUNDAMENTAL_FIELDS if field not in df.columns]
    if missing_columns:
        return [
            {
                "ticker": ticker,
                "name": name,
                "date": args.date,
                "ok": False,
                "source": "pykrx",
                "error": "pykrx_missing_fundamental_columns",
                "missing_columns": [field.lower() for field in missing_columns],
                "available_columns": [str(column) for column in df.columns],
            }
            for ticker, name in tickers.items()
        ]

    items: List[Dict[str, Any]] = []
    index_values = {str(index).zfill(6): index for index in df.index}
    for ticker, name in tickers.items():
        source_index = index_values.get(ticker)
        if source_index is None:
            items.append({
                "ticker": ticker,
                "name": name,
                "date": args.date,
                "ok": False,
                "source": "pykrx",
                "error": "ticker_missing_from_pykrx_result",
            })
            continue

        row = df.loc[source_index]
        item = {
            "ticker": ticker,
            "name": name,
            "date": args.date,
            "bps": clean_number(row.get("BPS")),
            "per": clean_number(row.get("PER")),
            "pbr": clean_number(row.get("PBR")),
            "eps": clean_number(row.get("EPS")),
            "div": clean_number(row.get("DIV")),
            "dps": clean_number(row.get("DPS")),
            "valuation_fields_available": True,
            "ok": True,
            "source": "pykrx",
        }
        missing_fields = [field.lower() for field in FUNDAMENTAL_FIELDS if clean_number(row.get(field)) is None]
        if missing_fields:
            item["missing_fields"] = missing_fields
        items.append(item)
    return items


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect fundamentals snapshot."""
    tickers = resolve_tickers(args)
    if not tickers:
        raise RuntimeError("No tickers resolved. Pass --tickers or populate picks/INDEX.md.")

    provider = "offline_sample" if args.offline_sample else args.provider

    if provider == "offline_sample":
        items = [offline_item(ticker, name, args.date) for ticker, name in tickers.items()]
    elif provider == "opendart":
        items = collect_opendart(args, tickers)
    elif provider == "pykrx":
        items = collect_pykrx(args, tickers)
    else:
        raise RuntimeError(f"Unsupported provider: {provider}")

    return {
        "generated_at": now_kst().isoformat(timespec="seconds"),
        "date": args.date,
        "market": args.market,
        "mode": "offline_sample" if provider == "offline_sample" else "live",
        "provider": provider,
        "source": provider if provider != "offline_sample" else "offline_fixture",
        "fields": [field.lower() for field in FUNDAMENTAL_FIELDS],
        "items": items,
    }


def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect Korean stock fundamentals.")
    parser.add_argument("--tickers", help="Comma-separated ticker list. Defaults to INDEX.md + paper rules.")
    parser.add_argument("--date", default=default_krx_date(), help="KRX date in YYYYMMDD format.")
    parser.add_argument("--provider", default="opendart", choices=("opendart", "pykrx", "offline_sample"))
    parser.add_argument("--market", default="ALL", choices=("KOSPI", "KOSDAQ", "KONEX", "ALL"))
    parser.add_argument("--business-year", default=default_business_year(), help="OpenDART business year in YYYY format.")
    parser.add_argument("--report-code", default="11011", choices=("11013", "11012", "11014", "11011"), help="OpenDART report code.")
    parser.add_argument("--opendart-api-key-env", default="OPENDART_API_KEY")
    parser.add_argument("--opendart-corp-cache", default=str(DEFAULT_CORP_CACHE))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Local env file for secrets. Defaults to .env.local.")
    parser.add_argument("--refresh-corp-codes", action="store_true")
    parser.add_argument("--index-path", default=str(DEFAULT_INDEX))
    parser.add_argument("--rules-path", default=str(DEFAULT_RULES))
    parser.add_argument("--market-snapshot-path", default=str(DEFAULT_MARKET_SNAPSHOT))
    parser.add_argument("--preopen-candidates-path", default=str(DEFAULT_PREOPEN_CANDIDATES))
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--offline-sample", action="store_true", help="Use deterministic fixture data without network.")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    if not re.match(r"^\d{8}$", args.date):
        print("ERROR --date must use YYYYMMDD format", file=sys.stderr)
        return 1
    if not re.match(r"^\d{4}$", args.business_year):
        print("ERROR --business-year must use YYYY format", file=sys.stderr)
        return 1
    try:
        provider = "offline_sample" if args.offline_sample else args.provider
        if provider == "offline_sample" and Path(args.snapshot_path) == DEFAULT_SNAPSHOT:
            raise RuntimeError("offline_sample cannot write the default operating snapshot. Pass --snapshot-path with a .test.json or .sample.json file.")
        snapshot = collect(args)
        write_json(Path(args.snapshot_path), snapshot)
        print(f"wrote {args.snapshot_path}")
        missing = [item["ticker"] for item in snapshot["items"] if not item.get("ok")]
        if missing:
            print(f"WARN missing fundamentals: {', '.join(missing)}")
            return 2
        return 0
    except RuntimeError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
