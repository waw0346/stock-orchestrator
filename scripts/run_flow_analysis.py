#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Collect and analyze 3-day consecutive foreign and pension fund buying/selling streaks.

Outputs:
  picks/cache/flow_streak_candidates.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

sys.path.insert(0, str(Path(__file__).parent))
from kiwoom_rest_client import KiwoomRestClient, KiwoomSettings


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "picks" / "cache" / "flow_streak_candidates.json"
KST = timezone(timedelta(hours=9))


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


def get_token(args: argparse.Namespace) -> str:
    """Return a Kiwoom access token from env or by client credentials."""
    settings = KiwoomSettings(
        app_key=args.app_key or os.environ.get("KIWOOM_APP_KEY", ""),
        app_secret=args.app_secret or os.environ.get("KIWOOM_APP_SECRET", ""),
        access_token=args.access_token or os.environ.get("KIWOOM_ACCESS_TOKEN", ""),
        base_url=args.base_url,
        timeout=args.timeout,
    )
    return KiwoomRestClient(settings).get_access_token()


def fetch_foreign_rank(client: KiwoomRestClient, relative_dt: str, trade_type: str, top: int) -> List[Dict[str, Any]]:
    """Fetch foreign rank for a single day using relative offset (e.g. '0', '1', '2') in ka10034."""
    # Note: trade_type "2" = buy, "1" = sell
    body = {
        "mrkt_tp": "000",
        "trde_tp": trade_type,
        "dt": relative_dt,
        "stex_tp": "1",
    }
    response = client.post_api("ka10034", "/api/dostk/rkinfo", body)
    items = response.get("for_dt_trde_upper") or response.get("items") or []
    return [
        {
            "ticker": str(item.get("stk_cd", "")).strip().lstrip("A").zfill(6),
            "name": str(item.get("stk_nm") or "").strip(),
            "net_buy": clean_int(item.get("netprps_qty")),
            "close": clean_abs_int(item.get("cur_prc")),
            "volume": clean_abs_int(item.get("trde_qty")),
        }
        for item in items[:top]
    ]


def fetch_pension_rank(client: KiwoomRestClient, date_str: str, trade_type: str, top: int) -> List[Dict[str, Any]]:
    """Fetch pension rank for a single day using ka10044."""
    formatted_date = date_str.replace("-", "")
    body = {
        "strt_dt": formatted_date,
        "end_dt": formatted_date,
        "mrkt_tp": "000",
        "org_tp": "7000",  # pension fund
        "trde_tp": trade_type,
        "stex_tp": "1"
    }
    response = client.post_api("ka10044", "/api/dostk/mrkcond", body)
    items = response.get("daly_orgn_trde_stk") or response.get("items") or []
    return [
        {
            "ticker": str(item.get("stk_cd", "")).strip().lstrip("A").zfill(6),
            "name": str(item.get("stk_nm") or "").strip(),
            "net_buy": clean_int(item.get("netprps_qty")),
            "close": clean_abs_int(item.get("cur_prc")),
            "volume": clean_abs_int(item.get("netprps_qty")),  # TODO: replace with actual volume when Kiwoom pension API exposes it
        }
        for item in items[:top]
    ]


def generate_recent_weekdays(n: int) -> List[str]:
    """Generate the last n calendar days that fall on weekdays (Mon-Fri) in KST, starting from today."""
    base = now_kst().date()
    days = []
    offset = 0
    # Search up to 15 days back to find enough weekdays
    while len(days) < n and offset < 15:
        day = base - timedelta(days=offset)
        if day.weekday() < 5:  # Monday to Friday
            days.append(day.isoformat())
        offset += 1
    return days


def collect_live_data(client: KiwoomRestClient, dates: List[str], consecutive_days: int, top_limit: int) -> Dict[str, Any]:
    """Query Kiwoom REST API to collect live foreigner and pension fund data for the recent weekdays."""
    # We want to find the most recent consecutive_days dates that actually return data for each type.
    # Foreigner rank
    foreign_buy_history: Dict[str, List[Dict[str, Any]]] = {}
    foreign_sell_history: Dict[str, List[Dict[str, Any]]] = {}
    
    # Pension fund rank
    pension_buy_history: Dict[str, List[Dict[str, Any]]] = {}
    pension_sell_history: Dict[str, List[Dict[str, Any]]] = {}

    print("Fetching live flow data from Kiwoom REST API...", file=sys.stderr)
    
    # Probe today's data to decide whether to include today or fallback to completed days.
    # Today is dates[0].
    today_str = dates[0]
    use_today = False
    
    try:
        # Check today's pension fund buy data
        pension_today_buy = fetch_pension_rank(client, today_str, "2", 10)
        # Check today's foreigner buy data (relative dt = "0")
        foreigner_today_buy = fetch_foreign_rank(client, "0", "2", 10)
        
        if len(pension_today_buy) >= 10 and len(foreigner_today_buy) >= 10:
            use_today = True
            print(f"Today ({today_str}) market data is complete. Scanning today + last {consecutive_days-1} days.", file=sys.stderr)
        else:
            print(f"Today ({today_str}) market data is incomplete (Pension: {len(pension_today_buy)}, Foreigner: {len(foreigner_today_buy)}). Scanning last {consecutive_days} completed days.", file=sys.stderr)
    except Exception as exc:
        print(f"Failed to probe today's data: {exc}. Defaulting to last {consecutive_days} completed days.", file=sys.stderr)

    # Select target dates and relative offsets based on probe
    if use_today:
        target_dates = dates[:consecutive_days]
        relative_offsets = [str(i) for i in range(consecutive_days)]
    else:
        target_dates = dates[1:consecutive_days+1]
        relative_offsets = [str(i) for i in range(1, consecutive_days+1)]

    print(f"Target trading days: {', '.join(target_dates)}", file=sys.stderr)
    
    for date_str, rel_offset in zip(target_dates, relative_offsets):
        # 1. Foreign buy
        try:
            items = fetch_foreign_rank(client, rel_offset, "2", top_limit)
            if items:
                foreign_buy_history[date_str] = items
                print(f"  [Foreign Buy] {date_str} (dt={rel_offset}): fetched {len(items)} items", file=sys.stderr)
        except Exception as exc:
            print(f"  [Foreign Buy] {date_str} (dt={rel_offset}) failed: {exc}", file=sys.stderr)

        # 2. Foreign sell
        try:
            items = fetch_foreign_rank(client, rel_offset, "1", top_limit)
            if items:
                foreign_sell_history[date_str] = items
                print(f"  [Foreign Sell] {date_str} (dt={rel_offset}): fetched {len(items)} items", file=sys.stderr)
        except Exception as exc:
            print(f"  [Foreign Sell] {date_str} (dt={rel_offset}) failed: {exc}", file=sys.stderr)

        # 3. Pension buy
        try:
            items = fetch_pension_rank(client, date_str, "2", top_limit)
            if items:
                pension_buy_history[date_str] = items
                print(f"  [Pension Buy] {date_str}: fetched {len(items)} items", file=sys.stderr)
        except Exception as exc:
            print(f"  [Pension Buy] {date_str} failed: {exc}", file=sys.stderr)

        # 4. Pension sell
        try:
            items = fetch_pension_rank(client, date_str, "1", top_limit)
            if items:
                pension_sell_history[date_str] = items
                print(f"  [Pension Sell] {date_str}: fetched {len(items)} items", file=sys.stderr)
        except Exception as exc:
            print(f"  [Pension Sell] {date_str} failed: {exc}", file=sys.stderr)

    return {
        "foreign_buy": foreign_buy_history,
        "foreign_sell": foreign_sell_history,
        "pension_buy": pension_buy_history,
        "pension_sell": pension_sell_history,
    }


def get_offline_sample_data(dates: List[str]) -> Dict[str, Any]:
    """Return deterministic mock data for testing."""
    # Let's ensure that the first 3 dates are populated with consecutive items.
    active_dates = dates[:3]
    
    # Mock data definitions (ticker, name, values per date offset)
    # values: net buy amount/shares. Positive for buy, negative for sell.
    foreign_buy_mobs = [
        ("005930", "삼성전자", [12000000000, 15000000000, 18000000000]),
        ("402340", "SK스퀘어", [7000000000, 9000000000, 11000000000]),
        ("000660", "SK하이닉스", [8000000000, -1000000000, 9000000000]), # not consecutive
        ("015760", "한국전력", [5000000000, 4000000000, 6000000000]),
        ("037560", "LG헬로비전", [100000000, 200000000, 300000000]),
        ("032640", "LG유플러스", [500000000, 600000000, 700000000]),
    ]
    
    foreign_sell_mobs = [
        ("017670", "SK텔레콤", [-5000000000, -6000000000, -7000000000]),
        ("020560", "아시아나항공", [-200000000, -300000000, -400000000]),
        ("091810", "티웨이항공", [-1000000000, -800000000, -1200000000]),
        ("005380", "현대차", [-8000000000, -9000000000, -10000000000]),
        ("035420", "NAVER", [-4000000000, -5000000000, -6000000000]),
    ]
    
    pension_buy_mobs = [
        ("000660", "SK하이닉스", [10000000000, 12000000000, 14000000000]),
        ("055550", "신한지주", [4000000000, 5000000000, 6000000000]),
        ("005930", "삼성전자", [12000000000, 10000000000, 15000000000]),
        ("035420", "NAVER", [3000000000, 2500000000, 4000000000]),
        ("003550", "LG", [1500000000, 1800000000, 2000000000]),
    ]
    
    pension_sell_mobs = [
        ("015760", "한국전력", [-3000000000, -4000000000, -5000000000]),
        ("373220", "LG에너지솔루션", [-8000000000, -10000000000, -12000000000]),
        ("066570", "LG전자", [-2000000000, -2500000000, -3000000000]),
        ("000270", "기아", [-4000000000, -3500000000, -5000000000]),
        ("010140", "삼성중공업", [-1000000000, -1500000000, -1200000000]),
    ]

    res = {"foreign_buy": {}, "foreign_sell": {}, "pension_buy": {}, "pension_sell": {}}

    for i, date_str in enumerate(active_dates):
        # Build Foreign Buy
        res["foreign_buy"][date_str] = []
        for ticker, name, vals in foreign_buy_mobs:
            val = vals[i]
            res["foreign_buy"][date_str].append({
                "ticker": ticker, "name": name, "net_buy": val, "close": 10000, "volume": 1000
            })
            
        # Build Foreign Sell
        res["foreign_sell"][date_str] = []
        for ticker, name, vals in foreign_sell_mobs:
            val = abs(vals[i]) # Store positive value representing the net sell amount
            res["foreign_sell"][date_str].append({
                "ticker": ticker, "name": name, "net_buy": -val, "close": 15000, "volume": 1500
            })

        # Build Pension Buy
        res["pension_buy"][date_str] = []
        for ticker, name, vals in pension_buy_mobs:
            val = vals[i]
            res["pension_buy"][date_str].append({
                "ticker": ticker, "name": name, "net_buy": val, "close": 50000, "volume": 5000
            })

        # Build Pension Sell
        res["pension_sell"][date_str] = []
        for ticker, name, vals in pension_sell_mobs:
            val = abs(vals[i])
            res["pension_sell"][date_str].append({
                "ticker": ticker, "name": name, "net_buy": -val, "close": 70000, "volume": 7000
            })
            
    return res


def compute_consecutive_streaks(history: Dict[str, List[Dict[str, Any]]], consecutive_days: int = 3, is_sell: bool = False) -> List[Dict[str, Any]]:
    """Scan history and return tickers that have consecutive positive/negative flow for target dates."""
    # Find the most recent dates that have data
    sorted_dates = sorted(history.keys(), reverse=True)
    if len(sorted_dates) < consecutive_days:
        return []
    
    target_dates = sorted_dates[:consecutive_days]
    
    # Track items by ticker for each day
    by_day_ticker: List[Dict[str, Dict[str, Any]]] = []
    for date_str in target_dates:
        day_dict = {row["ticker"]: row for row in history[date_str]}
        by_day_ticker.append(day_dict)
        
    # Find tickers that are present on all days with correct flow direction
    # Day 0 is most recent, Day (consecutive_days-1) is oldest.
    common_tickers: Set[str] = set(by_day_ticker[0].keys())
    for day_dict in by_day_ticker[1:]:
        common_tickers.intersection_update(day_dict.keys())
        
    candidates: List[Dict[str, Any]] = []
    for ticker in common_tickers:
        # Verify consecutive net buying/selling
        is_consecutive = True
        flow_sum = 0
        latest_flow = 0
        name = ""
        close = 0
        
        for i, day_dict in enumerate(by_day_ticker):
            item = day_dict[ticker]
            name = item["name"]
            close = item["close"]
            flow = item["net_buy"]
            
            if is_sell:
                # For selling, net_buy should be negative
                if flow >= 0:
                    is_consecutive = False
                    break
                flow_sum += abs(flow) # sum of net selling
                if i == 0:
                    latest_flow = abs(flow)
            else:
                # For buying, net_buy should be positive
                if flow <= 0:
                    is_consecutive = False
                    break
                flow_sum += flow
                if i == 0:
                    latest_flow = flow
                    
        if is_consecutive:
            candidates.append({
                "ticker": ticker,
                "name": name,
                "consecutive_days": consecutive_days,
                "latest_date": target_dates[0],
                "close": close,
                "net_flow_sum": flow_sum,
                "latest_net_flow": latest_flow,
            })
            
    # Sort candidates by cumulative net flow descending
    candidates.sort(key=lambda x: x["net_flow_sum"], reverse=True)
    return candidates


def print_markdown_report(result: Dict[str, Any]) -> None:
    """Print the final 3-day consecutive report in markdown format."""
    print("\n## 📊 실시간 외국인 및 연기금 3일 연속 매수/매도 스캔 결과")
    print(f"**스캔 기준시각**: {result['generated_at']} KST | **조회 모드**: {result['mode']}")
    print(f"**분석 적용 일자**: {', '.join(result['dates_analyzed'])}")
    
    categories = [
        ("🟢 외국인 3일 연속 순매수 Top 5", "foreign_buy_candidates", "순매수 합산 (3일)"),
        ("🔴 외국인 3일 연속 순매도 Top 5", "foreign_sell_candidates", "순매도 합산 (3일)"),
        ("🟢 연기금 3일 연속 순매수 Top 5", "pension_buy_candidates", "순매수 합산 (3일)"),
        ("🔴 연기금 3일 연속 순매도 Top 5", "pension_sell_candidates", "순매도 합산 (3일)"),
    ]
    
    for title, key, sum_label in categories:
        print(f"\n### {title}")
        items = result.get(key) or []
        if not items:
            print("  *조건을 충족하는 종목이 없습니다.*")
            continue
            
        print(f"| # | 종목명 | 종목코드 | 최근 종가 | {sum_label} | 최근 영업일 거래량/금액 |")
        print("|---|---|:---:|:---:|:---:|:---:|")
        for i, item in enumerate(items[:5], start=1):
            flow_sum_str = f"{item['net_flow_sum']:,}"
            latest_flow_str = f"{item['latest_net_flow']:,}"
            print(f"| {i} | {item['name']} | {item['ticker']} | {item['close']:,}원 | {flow_sum_str} | {latest_flow_str} |")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Collect and scan consecutive foreign & pension fund streaks.")
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--offline-sample", action="store_true", help="Run with deterministic sample data.")
    parser.add_argument("--top-limit", type=int, default=100, help="Number of ranks to fetch from Kiwoom API.")
    parser.add_argument("--base-url", default=os.environ.get("KIWOOM_BASE_URL", "https://api.kiwoom.com"))
    parser.add_argument("--access-token", default="")
    parser.add_argument("--app-key", default="")
    parser.add_argument("--app-secret", default="")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--consecutive-days", type=int, default=0, help="Streak length (e.g. 3 or 4). If 0, uses dynamic rules or defaults to 3.")
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        # Load dynamic rules if available
        config_path = ROOT / "picks" / "cache" / "dynamic_rules_config.json"
        consecutive_days = args.consecutive_days if args.consecutive_days > 0 else 3
        top_limit = args.top_limit
        
        if args.consecutive_days <= 0 and config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                params = config.get("parameters", {})
                consecutive_days = params.get("flow_streak_consecutive_days", 3)
                top_limit = params.get("top_limit", top_limit)
                print(f"Loaded dynamic parameter: flow_streak_consecutive_days = {consecutive_days}", file=sys.stderr)
                print(f"Loaded dynamic parameter: top_limit = {top_limit}", file=sys.stderr)
            except Exception as exc:
                print(f"Warning: Failed to load dynamic rules config: {exc}", file=sys.stderr)
        elif args.consecutive_days > 0:
            print(f"Using CLI parameter: consecutive_days = {consecutive_days}", file=sys.stderr)

        # Generate enough weekdays to probe
        recent_weekdays = generate_recent_weekdays(consecutive_days + 2)

        if args.offline_sample:
            raw_data = get_offline_sample_data(recent_weekdays)
        else:
            settings = KiwoomSettings(
                app_key=args.app_key or os.environ.get("KIWOOM_APP_KEY", ""),
                app_secret=args.app_secret or os.environ.get("KIWOOM_APP_SECRET", ""),
                access_token=args.access_token or os.environ.get("KIWOOM_ACCESS_TOKEN", ""),
                base_url=args.base_url,
                timeout=args.timeout,
            )
            client = KiwoomRestClient(settings)
            raw_data = collect_live_data(client, recent_weekdays, consecutive_days, top_limit)

        # Analyze streaks
        foreign_buy_streaks = compute_consecutive_streaks(raw_data["foreign_buy"], consecutive_days=consecutive_days, is_sell=False)
        foreign_sell_streaks = compute_consecutive_streaks(raw_data["foreign_sell"], consecutive_days=consecutive_days, is_sell=True)
        pension_buy_streaks = compute_consecutive_streaks(raw_data["pension_buy"], consecutive_days=consecutive_days, is_sell=False)
        pension_sell_streaks = compute_consecutive_streaks(raw_data["pension_sell"], consecutive_days=consecutive_days, is_sell=True)
        
        # Get active dates analyzed
        foreign_dates = sorted(raw_data["foreign_buy"].keys(), reverse=True)[:consecutive_days]
        pension_dates = sorted(raw_data["pension_buy"].keys(), reverse=True)[:consecutive_days]
        
        result = {
            "generated_at": now_kst().isoformat(timespec="seconds"),
            "mode": "offline_sample" if args.offline_sample else "live",
            "dates_analyzed": sorted(list(set(foreign_dates) | set(pension_dates)), reverse=True),
            "foreign_buy_candidates": foreign_buy_streaks[:5],
            "foreign_sell_candidates": foreign_sell_streaks[:5],
            "pension_buy_candidates": pension_buy_streaks[:5],
            "pension_sell_candidates": pension_sell_streaks[:5],
        }
        
        # Save output to cache
        Path(args.output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {args.output_path}", file=sys.stderr)
        
        # Print report
        print_markdown_report(result)
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
