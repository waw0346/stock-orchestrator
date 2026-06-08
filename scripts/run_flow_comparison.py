#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Compare intraday and after-close foreign and pension fund flows.
Classifies tickers into ETF and Stock categories and records divergences.

Outputs:
  picks/cache/flow_comparison_history.json
  picks/cache/flow_comparison_latest.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from kiwoom_rest_client import KiwoomRestClient, KiwoomSettings


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "picks" / "cache" / "flow_comparison_history.json"
DEFAULT_LATEST = ROOT / "picks" / "cache" / "flow_comparison_latest.json"
KST = timezone(timedelta(hours=9))

ETF_BRANDS = [
    "KODEX", "TIGER", "RISE", "PLUS", "ACE", "SOL", 
    "HANARO", "WOORI", "KOSEF", "ARIRANG", "KBSTAR"
]


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


def is_etf(name: str) -> bool:
    """Determine if a stock name belongs to an ETF based on brand keywords."""
    name_upper = name.upper()
    return any(brand in name_upper for brand in ETF_BRANDS)


def fetch_foreign_rank(client: KiwoomRestClient, relative_dt: str, trade_type: str, top: int) -> List[Dict[str, Any]]:
    """Fetch foreign rank for a single day using relative offset in ka10034."""
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
            "volume": clean_abs_int(item.get("netprps_qty")),  # quantity as volume proxy
        }
        for item in items[:top]
    ]


def generate_recent_weekdays(n: int) -> List[str]:
    """Generate the last n calendar days that fall on weekdays (Mon-Fri) in KST."""
    base = now_kst().date()
    days = []
    offset = 0
    while len(days) < n and offset < 15:
        day = base - timedelta(days=offset)
        if day.weekday() < 5:
            days.append(day.isoformat())
        offset += 1
    return days


def detect_mode_and_target(client: KiwoomRestClient, dates: List[str]) -> Tuple[str, str, str]:
    """Auto-detect target date, relative offset and execution mode."""
    # Today is dates[0]
    today_str = dates[0]
    kst_now = now_kst()
    
    # Check if today's market is open (or was open)
    try:
        pension_today = fetch_pension_rank(client, today_str, "2", 5)
        foreigner_today = fetch_foreign_rank(client, "0", "2", 5)
        
        # If today has data, we can analyze today
        if len(pension_today) >= 5 or len(foreigner_today) >= 5:
            # Determine mode based on time
            # Market session closes at 15:30 KST
            market_close_time = kst_now.replace(hour=15, minute=30, second=0, microsecond=0)
            if kst_now >= market_close_time:
                return "after_close", today_str, "0"
            else:
                return "intraday", today_str, "0"
    except Exception:
        pass
        
    # If today has no data (e.g. market hasn't opened yet, or holiday, or weekend)
    # Check if we are currently during market hours on a weekday
    is_weekday = kst_now.weekday() < 5
    market_open_time = kst_now.replace(hour=9, minute=0, second=0, microsecond=0)
    market_close_time = kst_now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    if is_weekday and market_open_time <= kst_now < market_close_time:
        return "intraday", today_str, "0"
        
    # Default fallback to the last completed trading day (dates[1])
    return "after_close", dates[1], "1"


def get_offline_mock_data(mode: str) -> Dict[str, List[Dict[str, Any]]]:
    """Generate deterministic mock data for intraday and after_close comparison testing."""
    # Base set of tickers
    # stocks: 005930 (Samsung), 000660 (Hynix), 001440 (Daehan Cable), 035420 (Naver)
    # etfs: 252670 (Kodex Inverse 2X), 122630 (Kodex Leverage), 472870 (Rise US30)
    
    if mode == "intraday":
        return {
            "foreign_buy": [
                {"ticker": "252670", "name": "KODEX 200선물인버스2X", "net_buy": 1000000, "close": 2000, "volume": 50000},
                {"ticker": "001440", "name": "대한전선", "net_buy": 500000, "close": 15000, "volume": 12000},
                {"ticker": "122630", "name": "KODEX 레버리지", "net_buy": -200000, "close": 18000, "volume": 8000},
                {"ticker": "005930", "name": "삼성전자", "net_buy": 2000000, "close": 75000, "volume": 150000},
            ],
            "foreign_sell": [
                {"ticker": "035420", "name": "NAVER", "net_buy": -800000, "close": 180000, "volume": 4000},
                {"ticker": "472870", "name": "RISE 미국30년국채엔화노출(합성 H)", "net_buy": -150000, "close": 8000, "volume": 20000},
            ],
            "pension_buy": [
                {"ticker": "000660", "name": "SK하이닉스", "net_buy": 300000, "close": 200000, "volume": 1500},
                {"ticker": "472870", "name": "RISE 미국30년국채엔화노출(합성 H)", "net_buy": 120000, "close": 8000, "volume": 20000},
            ],
            "pension_sell": [
                {"ticker": "005930", "name": "삼성전자", "net_buy": -400000, "close": 75000, "volume": 150000},
                {"ticker": "252670", "name": "KODEX 200선물인버스2X", "net_buy": -300000, "close": 2000, "volume": 50000},
            ]
        }
    else:  # after_close (simulate some end-of-day changes/divergence)
        return {
            "foreign_buy": [
                {"ticker": "252670", "name": "KODEX 200선물인버스2X", "net_buy": 1200000, "close": 2000, "volume": 60000}, # bought +200k at close
                {"ticker": "001440", "name": "대한전선", "net_buy": 300000, "close": 15000, "volume": 14000},  # sold -200k at close
                {"ticker": "122630", "name": "KODEX 레버리지", "net_buy": -100000, "close": 18000, "volume": 9000},  # bought back +100k
                {"ticker": "005930", "name": "삼성전자", "net_buy": 2800000, "close": 75000, "volume": 180000}, # bought +800k at close
            ],
            "foreign_sell": [
                {"ticker": "035420", "name": "NAVER", "net_buy": -1200000, "close": 180000, "volume": 6000}, # sold -400k more
                {"ticker": "472870", "name": "RISE 미국30년국채엔화노출(합성 H)", "net_buy": -150000, "close": 8000, "volume": 22000}, # unchanged
            ],
            "pension_buy": [
                {"ticker": "000660", "name": "SK하이닉스", "net_buy": 350000, "close": 200000, "volume": 2000},  # bought +50k
                {"ticker": "472870", "name": "RISE 미국30년국채엔화노출(합성 H)", "net_buy": 200000, "close": 8000, "volume": 22000}, # bought +80k
            ],
            "pension_sell": [
                {"ticker": "005930", "name": "삼성전자", "net_buy": -600000, "close": 75000, "volume": 180000}, # sold -200k more
                {"ticker": "252670", "name": "KODEX 200선물인버스2X", "net_buy": -100000, "close": 2000, "volume": 60000}, # bought back +200k at close
            ]
        }


def load_history(path: Path) -> Dict[str, Any]:
    """Load historical comparisons database."""
    if path.exists():
        try:
            return json.loads(path.read_text("utf-8"))
        except Exception as exc:
            print(f"Warning: Failed to load history JSON: {exc}. Starting fresh.", file=sys.stderr)
    return {}


def save_history(path: Path, data: Dict[str, Any]) -> None:
    """Save history database JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def classify_etfs_and_stocks(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separate records into ETFs and Stocks list."""
    etfs = []
    stocks = []
    seen = set()
    for row in records:
        key = row["ticker"]
        if key in seen:
            continue
        seen.add(key)
        if is_etf(row["name"]):
            etfs.append(row)
        else:
            stocks.append(row)
    return etfs, stocks


def map_flows_by_ticker(flow_list: List[Dict[str, Any]]) -> Dict[str, Tuple[str, int, int]]:
    """Map ticker to (name, net_buy, close)."""
    return {item["ticker"]: (item["name"], item["net_buy"], item["close"]) for item in flow_list}


def calculate_divergence(intraday_data: Dict[str, Any], after_close_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Calculate flow divergences between intraday and after_close snapshots."""
    # Compare Foreigner Flows
    # Merge buy and sell lists
    intra_for = Map_intraday_flows(intraday_data, "foreigner")
    close_for = Map_close_flows(after_close_data, "foreigner")
    
    # Compare Pension Flows
    intra_pen = Map_intraday_flows(intraday_data, "pension")
    close_pen = Map_close_flows(after_close_data, "pension")
    
    # Compute Foreigner Divergence
    for_divs = []
    for ticker in set(intra_for.keys()) | set(close_for.keys()):
        name = close_for.get(ticker, (intra_for.get(ticker, ("", 0, 0))[0], 0, 0))[0]
        close = close_for.get(ticker, (0, 0, 0))[2] or intra_for.get(ticker, (0, 0, 0))[2]
        
        val_intra = intra_for.get(ticker, ("", 0, 0))[1]
        val_close = close_for.get(ticker, ("", 0, 0))[1]
        div = val_close - val_intra
        
        for_divs.append({
            "ticker": ticker,
            "name": name,
            "close": close,
            "intraday": val_intra,
            "after_close": val_close,
            "divergence": div
        })
        
    # Compute Pension Divergence
    pen_divs = []
    for ticker in set(intra_pen.keys()) | set(close_pen.keys()):
        name = close_pen.get(ticker, (intra_pen.get(ticker, ("", 0, 0))[0], 0, 0))[0]
        close = close_pen.get(ticker, (0, 0, 0))[2] or intra_pen.get(ticker, (0, 0, 0))[2]
        
        val_intra = intra_pen.get(ticker, ("", 0, 0))[1]
        val_close = close_pen.get(ticker, ("", 0, 0))[1]
        div = val_close - val_intra
        
        pen_divs.append({
            "ticker": ticker,
            "name": name,
            "close": close,
            "intraday": val_intra,
            "after_close": val_close,
            "divergence": div
        })
        
    return {
        "foreigner": for_divs,
        "pension": pen_divs
    }


def Map_intraday_flows(snapshot: Dict[str, Any], investor_type: str) -> Dict[str, Tuple[str, int, int]]:
    """Helper to map intraday flows by ticker."""
    res = {}
    if investor_type == "foreigner":
        res.update(map_flows_by_ticker(snapshot.get("foreign_buy") or []))
        res.update(map_flows_by_ticker(snapshot.get("foreign_sell") or []))
    else:
        res.update(map_flows_by_ticker(snapshot.get("pension_buy") or []))
        res.update(map_flows_by_ticker(snapshot.get("pension_sell") or []))
    return res


def Map_close_flows(snapshot: Dict[str, Any], investor_type: str) -> Dict[str, Tuple[str, int, int]]:
    """Helper to map close flows by ticker."""
    # Close flows structure is same as intraday list format
    return Map_intraday_flows(snapshot, investor_type)


def print_markdown_comparison_report(latest: Dict[str, Any]) -> None:
    """Print markdown report to stdout."""
    print(f"\n## ⚖️ 실시간 수급 비교 및 ETF 자체 필터링 결과")
    print(f"**조회 일자**: {latest['date']} | **기준 시각**: {latest['generated_at']} KST | **조회 모드**: {latest['mode']}")
    print(f"**비교 분석 여부**: {'성공 (장중 vs 장마감 대비 괴리 분석 완료)' if latest['has_comparison'] else '대기 (장중 데이터 없음 - 마감 결과만 출력)'}")
    
    # 1. ETF vs Stock 분류 결과 요약
    print("\n### 🏷️ 당일 수급 상위 자율 분류 (ETF vs 주식)")
    
    # Helper to print table
    def print_class_table(title: str, items: List[Dict[str, Any]], sum_label: str):
        print(f"\n#### {title} (Top 5)")
        if not items:
            print("  *수집된 종목이 없습니다.*")
            return
        print(f"| # | 종목명 | 종목코드 | 최근가 | {sum_label} |")
        print("|---|---|:---:|:---:|:---:|")
        for i, item in enumerate(items[:5], start=1):
            print(f"| {i} | {item['name']} | {item['ticker']} | {item['close']:,}원 | {item['net_buy']:,} |")

    # ETFs
    print_class_table("🟢 외국인 순매수 ETF", latest["etfs"]["foreign_buy"], "순매수")
    print_class_table("🔴 외국인 순매도 ETF", latest["etfs"]["foreign_sell"], "순매도")
    print_class_table("🟢 연기금 순매수 ETF", latest["etfs"]["pension_buy"], "순매수")
    print_class_table("🔴 연기금 순매도 ETF", latest["etfs"]["pension_sell"], "순매도")
    
    # Stocks
    print_class_table("🟢 외국인 순매수 일반 주식", latest["stocks"]["foreign_buy"], "순매수")
    print_class_table("🔴 외국인 순매도 일반 주식", latest["stocks"]["foreign_sell"], "순매도")
    print_class_table("🟢 연기금 순매수 일반 주식", latest["stocks"]["pension_buy"], "순매수")
    print_class_table("🔴 연기금 순매도 일반 주식", latest["stocks"]["pension_sell"], "순매도")
    
    # 2. Divergence 결과 출력
    if latest["has_comparison"]:
        print("\n### ⚡ 장마감 직전 수급 괴리(Divergence) 분석")
        print("> 장마감 동시호가 또는 오후 후반부에 세력의 매수 강도가 급증(Positive)하거나 급감(Negative)한 종목군입니다.")
        
        def print_div_table(title: str, divs: List[Dict[str, Any]]):
            print(f"\n#### {title}")
            if not divs:
                print("  *해당 조건의 종목이 없습니다.*")
                return
            print("| # | 종목명 | 종목코드 | 장중 수급 | 장마감 수급 | 종가 괴리도 |")
            print("|---|---|:---:|:---:|:---:|:---:|")
            for i, item in enumerate(divs[:5], start=1):
                print(f"| {i} | {item['name']} | {item['ticker']} | {item['intraday']:,} | {item['after_close']:,} | **{item['divergence']:+,}** |")

        # Foreigner Divergences
        print_div_table("📈 외국인 종가 매수 유입 (주식 Positive Divergence)", latest["divergences"]["stock_foreigner_positive"])
        print_div_table("📉 외국인 종가 매도 이탈 (주식 Negative Divergence)", latest["divergences"]["stock_foreigner_negative"])
        print_div_table("📈 외국인 종가 매수 유입 (ETF Positive Divergence)", latest["divergences"]["etf_foreigner_positive"])
        print_div_table("📉 외국인 종가 매도 이탈 (ETF Negative Divergence)", latest["divergences"]["etf_foreigner_negative"])
        
        # Pension Divergences
        print_div_table("📈 연기금 종가 매수 유입 (주식 Positive Divergence)", latest["divergences"]["stock_pension_positive"])
        print_div_table("📉 연기금 종가 매도 이탈 (주식 Negative Divergence)", latest["divergences"]["stock_pension_negative"])
        print_div_table("📈 연기금 종가 매수 유입 (ETF Positive Divergence)", latest["divergences"]["etf_pension_positive"])
        print_div_table("📉 연기금 종가 매도 이탈 (ETF Negative Divergence)", latest["divergences"]["etf_pension_negative"])


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Filter ETF/Stocks and compare Intraday vs After-Close flows.")
    parser.add_argument("--history-path", default=str(DEFAULT_HISTORY))
    parser.add_argument("--latest-path", default=str(DEFAULT_LATEST))
    parser.add_argument("--mode", default="", choices=["intraday", "after_close"], help="Override execution mode.")
    parser.add_argument("--offline-sample", action="store_true", help="Run with deterministic sample data.")
    parser.add_argument("--top-limit", type=int, default=50, help="Number of ranks to fetch.")
    parser.add_argument("--base-url", default=os.environ.get("KIWOOM_BASE_URL", "https://api.kiwoom.com"))
    parser.add_argument("--access-token", default="")
    parser.add_argument("--app-key", default="")
    parser.add_argument("--app-secret", default="")
    parser.add_argument("--timeout", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    """CLI entry point."""
    configure_stdio()
    args = parse_args()
    try:
        recent_weekdays = generate_recent_weekdays(5)
        history = load_history(Path(args.history_path))
        
        target_date = recent_weekdays[0]
        mode = args.mode
        rel_offset = "0"
        
        # 1. Fetch raw data
        if args.offline_sample:
            # Under offline sample, mode auto-detect or default
            if not mode:
                mode = "intraday"
            raw_flows = get_offline_mock_data(mode)
            print(f"Running in OFFLINE_SAMPLE mode. Simulating '{mode}' for {target_date}.", file=sys.stderr)
        else:
            settings = KiwoomSettings(
                app_key=args.app_key or os.environ.get("KIWOOM_APP_KEY", ""),
                app_secret=args.app_secret or os.environ.get("KIWOOM_APP_SECRET", ""),
                access_token=args.access_token or os.environ.get("KIWOOM_ACCESS_TOKEN", ""),
                base_url=args.base_url,
                timeout=args.timeout,
            )
            client = KiwoomRestClient(settings)
            
            # Detect mode and target dynamically if not explicitly overridden
            detected_mode, detected_date, detected_offset = detect_mode_and_target(client, recent_weekdays)
            if not mode:
                mode = detected_mode
            target_date = detected_date
            rel_offset = detected_offset
            
            print(f"Detected mode: {mode}, target date: {target_date} (dt={rel_offset})", file=sys.stderr)
            
            raw_flows = {
                "foreign_buy": fetch_foreign_rank(client, rel_offset, "2", args.top_limit),
                "foreign_sell": fetch_foreign_rank(client, rel_offset, "1", args.top_limit),
                "pension_buy": fetch_pension_rank(client, target_date, "2", args.top_limit),
                "pension_sell": fetch_pension_rank(client, target_date, "1", args.top_limit)
            }
            
        # 2. Separate ETFs vs Stocks for display
        etf_f_buy, stock_f_buy = classify_etfs_and_stocks(raw_flows["foreign_buy"])
        etf_f_sell, stock_f_sell = classify_etfs_and_stocks(raw_flows["foreign_sell"])
        etf_p_buy, stock_p_buy = classify_etfs_and_stocks(raw_flows["pension_buy"])
        etf_p_sell, stock_p_sell = classify_etfs_and_stocks(raw_flows["pension_sell"])
        
        # 3. Update comparison database
        if target_date not in history:
            history[target_date] = {}
            
        history[target_date][mode] = {
            "generated_at": now_kst().isoformat(timespec="seconds"),
            "foreign_buy": raw_flows["foreign_buy"],
            "foreign_sell": raw_flows["foreign_sell"],
            "pension_buy": raw_flows["pension_buy"],
            "pension_sell": raw_flows["pension_sell"]
        }
        save_history(Path(args.history_path), history)
        print(f"Updated {args.history_path} for date {target_date} and mode '{mode}'", file=sys.stderr)
        
        # 4. Perform comparison if mode is after_close and intraday exists
        has_comparison = False
        divergences = {}
        
        stock_for_pos, stock_for_neg = [], []
        etf_for_pos, etf_for_neg = [], []
        stock_pen_pos, stock_pen_neg = [], []
        etf_pen_pos, etf_pen_neg = [], []
        
        if mode == "after_close" and "intraday" in history[target_date]:
            has_comparison = True
            divs = calculate_divergence(history[target_date]["intraday"], history[target_date]["after_close"])
            
            # Sort divergences
            # Foreigner
            for_div_list = divs["foreigner"]
            # Classify
            etf_for_divs = [d for d in for_div_list if is_etf(d["name"])]
            stock_for_divs = [d for d in for_div_list if not is_etf(d["name"])]
            
            # Sort ETF
            etf_for_pos = sorted([d for d in etf_for_divs if d["divergence"] > 0], key=lambda x: x["divergence"], reverse=True)
            etf_for_neg = sorted([d for d in etf_for_divs if d["divergence"] < 0], key=lambda x: x["divergence"])
            
            # Sort Stock
            stock_for_pos = sorted([d for d in stock_for_divs if d["divergence"] > 0], key=lambda x: x["divergence"], reverse=True)
            stock_for_neg = sorted([d for d in stock_for_divs if d["divergence"] < 0], key=lambda x: x["divergence"])
            
            # Pension
            pen_div_list = divs["pension"]
            # Classify
            etf_pen_divs = [d for d in pen_div_list if is_etf(d["name"])]
            stock_pen_divs = [d for d in pen_div_list if not is_etf(d["name"])]
            
            # Sort ETF
            etf_pen_pos = sorted([d for d in etf_pen_divs if d["divergence"] > 0], key=lambda x: x["divergence"], reverse=True)
            etf_pen_neg = sorted([d for d in etf_pen_divs if d["divergence"] < 0], key=lambda x: x["divergence"])
            
            # Sort Stock
            stock_pen_pos = sorted([d for d in stock_pen_divs if d["divergence"] > 0], key=lambda x: x["divergence"], reverse=True)
            stock_pen_neg = sorted([d for d in stock_pen_divs if d["divergence"] < 0], key=lambda x: x["divergence"])
            
        # 5. Build latest result
        latest_report = {
            "date": target_date,
            "mode": mode,
            "generated_at": now_kst().isoformat(timespec="seconds"),
            "has_comparison": has_comparison,
            "etfs": {
                "foreign_buy": etf_f_buy[:10],
                "foreign_sell": etf_f_sell[:10],
                "pension_buy": etf_p_buy[:10],
                "pension_sell": etf_p_sell[:10]
            },
            "stocks": {
                "foreign_buy": stock_f_buy[:10],
                "foreign_sell": stock_f_sell[:10],
                "pension_buy": stock_p_buy[:10],
                "pension_sell": stock_p_sell[:10]
            },
            "divergences": {
                "stock_foreigner_positive": stock_for_pos[:5],
                "stock_foreigner_negative": stock_for_neg[:5],
                "etf_foreigner_positive": etf_for_pos[:5],
                "etf_foreigner_negative": etf_for_neg[:5],
                "stock_pension_positive": stock_pen_pos[:5],
                "stock_pension_negative": stock_pen_neg[:5],
                "etf_pension_positive": etf_pen_pos[:5],
                "etf_pension_negative": etf_pen_neg[:5]
            }
        }
        
        save_history(Path(args.latest_path), latest_report)
        print(f"wrote {args.latest_path}", file=sys.stderr)
        
        # 6. Render report
        print_markdown_comparison_report(latest_report)
        return 0
    except Exception as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
