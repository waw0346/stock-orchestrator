#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Collect Fiscal.ai company profile snapshots without printing secrets.

Outputs:
  picks/cache/fiscal_ai_snapshot.json
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from lib.env import read_env_file_value


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_FILE = ROOT / ".env.local"
DEFAULT_SNAPSHOT = ROOT / "picks" / "cache" / "fiscal_ai_snapshot.json"
FISCAL_PROFILE_URL = "https://api.fiscal.ai/v2/company/profile"
FISCAL_COMPANIES_URL = "https://api.fiscal.ai/v2/companies-list"
FISCAL_TOP_NEWS_URL = "https://api.fiscal.ai/v1/top-news"
FISCAL_COMPANY_NEWS_URL = "https://api.fiscal.ai/v1/company/news"
INVESTMENT_EVENT_TYPES = "earnings,guidance,buyback,ma,partnership,financing,analyst,market_commentary,technology,product_launch,expansion,regulatory"
KST = timezone(timedelta(hours=9))


def configure_stdio() -> None:
    """Prefer UTF-8 console output when the runtime supports it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def now_kst() -> str:
    """Return current KST timestamp."""
    return datetime.now(KST).isoformat(timespec="seconds")





def write_json(path: Path, data: Any) -> None:
    """Write JSON with UTF-8 formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_company_keys(raw: str) -> List[str]:
    """Parse comma-separated company keys."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def offline_profile(company_key: str) -> Dict[str, Any]:
    """Return deterministic Fiscal.ai profile fixture."""
    ticker = company_key.split("_")[-1]
    return {
        "company_key": company_key,
        "ticker": ticker,
        "name": {
            "MSFT": "Microsoft Corporation",
            "NVDA": "NVIDIA Corporation",
            "AAPL": "Apple Inc.",
        }.get(ticker, ticker),
        "ok": True,
        "source": "offline_fixture",
        "datasets": ["profile", "financials", "ratios", "news"],
    }


def fiscal_profile(company_key: str, api_key: str, timeout: int) -> Dict[str, Any]:
    """Fetch one Fiscal.ai company profile."""
    query = urllib.parse.urlencode({"companyKey": company_key})
    request = urllib.request.Request(
        f"{FISCAL_PROFILE_URL}?{query}",
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "stock-orchestrator/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {
            "company_key": company_key,
            "ticker": data.get("ticker") or company_key.split("_")[-1],
            "name": data.get("name") or data.get("companyName") or company_key,
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "country": data.get("country"),
            "exchange": data.get("exchange"),
            "ok": True,
            "source": "fiscal_ai",
        }
    except urllib.error.HTTPError as exc:
        return {"company_key": company_key, "ok": False, "source": "fiscal_ai", "error": f"http_{exc.code}"}
    except Exception as exc:
        return {"company_key": company_key, "ok": False, "source": "fiscal_ai", "error": exc.__class__.__name__}


def fiscal_companies_list(api_key: str, timeout: int, page_number: int, page_size: int) -> Dict[str, Any]:
    """Fetch one Fiscal.ai companies-list page."""
    query = urllib.parse.urlencode({"pageNumber": page_number, "pageSize": page_size})
    request = urllib.request.Request(
        f"{FISCAL_COMPANIES_URL}?{query}",
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "stock-orchestrator/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    raw_items = data.get("data") or data.get("items") or data.get("companies") or ([] if not isinstance(data, list) else data)
    items = []
    for row in raw_items[:page_size]:
        if not isinstance(row, dict):
            continue
        items.append({
            "company_key": row.get("companyKey") or row.get("company_key"),
            "ticker": row.get("ticker"),
            "name": row.get("name") or row.get("companyName"),
            "exchange": row.get("exchange"),
            "mic_code": row.get("micCode") or row.get("mic"),
            "country": row.get("country"),
            "datasets": row.get("datasets") or row.get("availableData") or row.get("dataAvailable"),
        })
    return {
        "page_number": page_number,
        "page_size": page_size,
        "raw_shape": "list" if isinstance(data, list) else "object",
        "items": items,
    }


def fiscal_top_news(api_key: str, timeout: int, page_size: int, event_types: str, min_importance: int, max_importance: int) -> Dict[str, Any]:
    """Fetch recent investment-relevant Fiscal.ai top news."""
    query = urllib.parse.urlencode({
        "pageSize": page_size,
        "eventType": event_types,
        "minImportance": min_importance,
        "maxImportance": max_importance,
    })
    request = urllib.request.Request(
        f"{FISCAL_TOP_NEWS_URL}?{query}",
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "stock-orchestrator/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    items = filter_investment_news(
        normalize_news_items(extract_news_items(data), page_size),
        event_types,
        min_importance,
        max_importance,
    )
    return {
        "event_types": event_types,
        "min_importance": min_importance,
        "max_importance": max_importance,
        "page_size": page_size,
        "raw_shape": "list" if isinstance(data, list) else "object",
        "items": items,
    }


def extract_news_items(data: Any) -> List[Any]:
    """Extract Fiscal.ai news rows from list or object-shaped responses."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("data", "items", "news", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def normalize_news_items(raw_items: List[Any], page_size: int) -> List[Dict[str, Any]]:
    """Normalize Fiscal.ai news rows."""
    items = []
    for row in raw_items[:page_size]:
        if not isinstance(row, dict):
            continue
        items.append({
            "company_key": row.get("companyKey") or row.get("company_key"),
            "ticker": row.get("ticker"),
            "company": row.get("companyName") or row.get("name"),
            "title": row.get("title") or row.get("headline"),
            "summary": row.get("summary") or row.get("description"),
            "event_type": row.get("eventType"),
            "importance": row.get("importance"),
            "source_url": row.get("sourceUrl") or row.get("url"),
            "collected_at": row.get("collectedAt") or row.get("publishedAt") or row.get("date"),
        })
    return items


def filter_investment_news(items: List[Dict[str, Any]], event_types: str, min_importance: int, max_importance: int) -> List[Dict[str, Any]]:
    """Keep news rows that match investment-relevant event and importance limits."""
    allowed_events = {event.strip() for event in event_types.split(",") if event.strip()}
    filtered = []
    for item in items:
        event_type = item.get("event_type")
        importance = item.get("importance")
        try:
            importance_value = int(importance)
        except (TypeError, ValueError):
            importance_value = None
        if allowed_events and event_type and event_type not in allowed_events:
            continue
        if importance_value is not None and (importance_value < min_importance or importance_value > max_importance):
            continue
        filtered.append(item)
    return filtered


def fiscal_company_news(company_key: str, api_key: str, timeout: int, page_size: int, event_types: str, min_importance: int, max_importance: int) -> List[Dict[str, Any]]:
    """Fetch company news for one Fiscal.ai company key."""
    query = urllib.parse.urlencode({"companyKey": company_key})
    request = urllib.request.Request(
        f"{FISCAL_COMPANY_NEWS_URL}?{query}",
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
            "User-Agent": "stock-orchestrator/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    items = filter_investment_news(
        normalize_news_items(extract_news_items(data), page_size),
        event_types,
        min_importance,
        max_importance,
    )
    for item in items:
        item["company_key"] = item.get("company_key") or company_key
    return items


def offline_news() -> List[Dict[str, Any]]:
    """Return deterministic investment-news fixture."""
    return [
        {
            "company_key": "NASDAQ_NVDA",
            "ticker": "NVDA",
            "company": "NVIDIA Corporation",
            "title": "NVIDIA announces AI infrastructure partnership",
            "summary": "Partnership expands AI infrastructure demand signal.",
            "event_type": "partnership",
            "importance": 2,
            "source": "offline_fixture",
        },
        {
            "company_key": "NASDAQ_MSFT",
            "ticker": "MSFT",
            "company": "Microsoft Corporation",
            "title": "Microsoft updates cloud and AI guidance",
            "summary": "Guidance update is relevant to AI software and cloud demand.",
            "event_type": "guidance",
            "importance": 2,
            "source": "offline_fixture",
        },
    ]


def collect(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect Fiscal.ai profiles."""
    api_key = os.environ.get(args.api_key_env, "").strip() or read_env_file_value(Path(args.env_file), args.api_key_env)
    if not args.offline_sample and not api_key:
        raise RuntimeError(f"{args.api_key_env} is not set in environment or {args.env_file}.")
    if args.list_companies:
        if args.offline_sample:
            items = [offline_profile(key) for key in parse_company_keys(args.company_keys)]
            return {
                "generated_at": now_kst(),
                "mode": "offline_sample",
                "source": "offline_fixture",
                "list_companies": True,
                "items": items,
            }
        page = fiscal_companies_list(api_key, args.timeout, args.page_number, args.page_size)
        return {
            "generated_at": now_kst(),
            "mode": "live",
            "source": "fiscal_ai",
            "list_companies": True,
            **page,
            "note": "Use this snapshot to inspect Fiscal.ai plan/company coverage.",
        }
    if args.top_news:
        if args.offline_sample:
            return {
                "generated_at": now_kst(),
                "mode": "offline_sample",
                "source": "offline_fixture",
                "top_news": True,
                "items": offline_news(),
                "note": "Offline investment-news fixture.",
            }
        news = fiscal_top_news(api_key, args.timeout, args.page_size, args.event_types, args.min_importance, args.max_importance)
        return {
            "generated_at": now_kst(),
            "mode": "live",
            "source": "fiscal_ai",
            "top_news": True,
            **news,
            "note": "Recent Fiscal.ai investment-relevant news. Use as research context, not direct trading instructions.",
        }
    if args.company_news:
        company_keys = parse_company_keys(args.company_keys)
        if args.offline_sample:
            return {
                "generated_at": now_kst(),
                "mode": "offline_sample",
                "source": "offline_fixture",
                "company_news": True,
                "items": offline_news(),
            }
        items: List[Dict[str, Any]] = []
        failures = []
        for key in company_keys:
            try:
                items.extend(fiscal_company_news(key, api_key, args.timeout, args.page_size, args.event_types, args.min_importance, args.max_importance))
            except urllib.error.HTTPError as exc:
                failures.append({"company_key": key, "error": f"http_{exc.code}"})
            except Exception as exc:
                failures.append({"company_key": key, "error": exc.__class__.__name__})
        return {
            "generated_at": now_kst(),
            "mode": "live",
            "source": "fiscal_ai",
            "company_news": True,
            "items": items,
            "failures": failures,
            "note": "Recent Fiscal.ai company news for allowed company keys.",
        }

    company_keys = parse_company_keys(args.company_keys)
    if not company_keys:
        raise RuntimeError("No company keys supplied.")
    items = [offline_profile(key) if args.offline_sample else fiscal_profile(key, api_key, args.timeout) for key in company_keys]
    return {
        "generated_at": now_kst(),
        "mode": "offline_sample" if args.offline_sample else "live",
        "source": "offline_fixture" if args.offline_sample else "fiscal_ai",
        "items": items,
        "note": "Fiscal.ai is used for company profile/fundamental/news enrichment, not Korean investor flow.",
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect Fiscal.ai company profiles.")
    parser.add_argument("--company-keys", default="NASDAQ_MSFT,NASDAQ_NVDA,NASDAQ_AAPL")
    parser.add_argument("--snapshot-path", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--api-key-env", default="FISCAL_AI_API_KEY")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--list-companies", action="store_true")
    parser.add_argument("--top-news", action="store_true")
    parser.add_argument("--company-news", action="store_true")
    parser.add_argument("--page-number", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--event-types", default=INVESTMENT_EVENT_TYPES)
    parser.add_argument("--min-importance", type=int, default=1)
    parser.add_argument("--max-importance", type=int, default=3)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        snapshot = collect(args)
        write_json(Path(args.snapshot_path), snapshot)
        print(f"wrote {args.snapshot_path}")
        failed = [
            item.get("company_key") or item.get("ticker") or "unknown"
            for item in snapshot["items"]
            if item.get("ok") is False
        ]
        if failed and not args.offline_sample and not snapshot.get("list_companies"):
            print(f"WARN missing Fiscal.ai profiles: {', '.join(failed)}")
            return 2
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
