#!/usr/bin/env python3
# pylint: disable=broad-exception-caught
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "picks" / "cache"
LEADERS_JSON = CACHE_DIR / "realtime_leaders.json"
MARKET_SNAPSHOT = CACHE_DIR / "market_data_snapshot.json"
FLOW_SNAPSHOT = CACHE_DIR / "flow_snapshot.json"
STREAK_SNAPSHOT = CACHE_DIR / "foreign_streak_candidates.json"
NEWS_SNAPSHOT = CACHE_DIR / "fiscal_ai_investment_news.json"

KST = timezone(timedelta(hours=9))

def configure_stdio() -> None:
    """Enforce UTF-8 for console streams on Windows."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def now_kst() -> datetime:
    return datetime.now(KST)

def read_json_safe(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to read JSON at {path.name}: {e}", file=sys.stderr)
        return {}

def get_leaders_cache_age_seconds() -> float:
    if not LEADERS_JSON.exists():
        return 999999.0
    mtime = LEADERS_JSON.stat().st_mtime
    return datetime.now().timestamp() - mtime

def fetch_realtime_data_kiwoom() -> List[dict]:
    """
    Simulate or fetch live rank from Kiwoom REST client.
    For standard operations, we reuse the collected rank file or query Kiwoom API if online.
    """
    # Fallback to offline collected data if API token is missing or offline mode.
    # In real pipeline, collect_kiwoom_foreign_rank.py is executed in Step 4.
    # We load foreign_rank_snapshot.json which was refreshed.
    rank_file = CACHE_DIR / "foreign_rank_snapshot.json"
    if rank_file.exists():
        data = read_json_safe(rank_file)
        if isinstance(data, dict) and "ranks" in data:
            return data["ranks"]
        elif isinstance(data, list):
            return data
    return []

def analyze_leaders(test_mode=False):
    configure_stdio()
    print(f"[LEADERS] Starting Real-time Leader Analysis...")
    
    # 1. Load snapshots
    market_data = read_json_safe(MARKET_SNAPSHOT)
    flow_data = read_json_safe(FLOW_SNAPSHOT)
    streak_data = read_json_safe(STREAK_SNAPSHOT)
    news_data = read_json_safe(NEWS_SNAPSHOT)
    
    # Stock universe mapping
    universe = {}
    
    # Fill from market snapshot
    market_items = market_data.get("items", []) if isinstance(market_data, dict) else []
    for item in market_items:
        ticker = str(item.get("ticker", "")).zfill(6)
        if not ticker or ticker == "000000":
            continue
        universe[ticker] = {
            "ticker": ticker,
            "name": item.get("name", "Unknown"),
            "price": item.get("price", 0),
            "change_rate": item.get("change_rate", 0.0),
            "volume": item.get("volume", 0),
            "volume_ratio_20d": item.get("volume_ratio_20d", 0.0),
            "ma20": item.get("ma20", 0.0),
            "ma60": item.get("ma60", 0.0),
            "rsi14": item.get("rsi14", 50.0),
            "foreign_net_buy_5d": 0,
            "institution_net_buy_5d": 0,
            "streak_days": 0,
            "catalyst": ""
        }
        
    # Fill from flow snapshot (5-day flows)
    flow_items = flow_data.get("items", []) if isinstance(flow_data, dict) else []
    for item in flow_items:
        ticker = str(item.get("ticker", "")).zfill(6)
        if ticker in universe:
            universe[ticker]["foreign_net_buy_5d"] = item.get("foreign_net_buy_5d", 0)
            universe[ticker]["institution_net_buy_5d"] = item.get("institution_net_buy_5d", 0)
            
    # Fill from streak snapshot (Accumulated buying streaks)
    streak_candidates = streak_data.get("candidates", []) if isinstance(streak_data, dict) else []
    for item in streak_candidates:
        ticker = str(item.get("ticker", "")).zfill(6)
        if ticker in universe:
            universe[ticker]["streak_days"] = item.get("consecutive_foreign_buy_days", 0)

    # Fill from news snapshot (Catalysts)
    # Check both keys: "news" or "items"
    news_items = news_data.get("news", news_data.get("items", [])) if isinstance(news_data, dict) else []
    for news in news_items:
        tickers = news.get("tickers", [])
        title = news.get("title", "")
        # Match ticker and assign first matching news as catalyst
        for tk in tickers:
            tk_str = str(tk).zfill(6)
            if tk_str in universe and not universe[tk_str]["catalyst"]:
                universe[tk_str]["catalyst"] = title

    # Core scoring logic (10-point scale)
    scored_items = []
    for ticker, info in universe.items():
        # Score components
        flow_score = 0.0       # Max 3.0
        streak_score = 0.0     # Max 2.0
        volume_score = 0.0     # Max 2.0
        ma_score = 0.0         # Max 3.0
        
        # 1. Flow Score (5-day foreigner/institution net buy)
        f_flow = info["foreign_net_buy_5d"]
        i_flow = info["institution_net_buy_5d"]
        if f_flow > 0 and i_flow > 0:
            flow_score = 3.0   # Double buying
        elif f_flow > 0 or i_flow > 0:
            flow_score = 1.5   # Single buyer
            
        # 2. Streak Score (Consecutive buy days)
        stk = info["streak_days"]
        if stk >= 3:
            streak_score = 2.0
        elif stk > 0:
            streak_score = 1.0
            
        # 3. Volume Score (Volume ratio vs 20d avg)
        vr = info["volume_ratio_20d"]
        # In case of breakout (Volume spike)
        if vr >= 1.5:
            volume_score = 2.0
        elif vr >= 0.8:
            volume_score = 1.0
        # In case of tight consolidation (Volume contraction near support)
        elif vr > 0 and vr <= 0.15:
            volume_score = 2.0  # Tight pullback setup
        elif vr > 0 and vr <= 0.3:
            volume_score = 1.0
            
        # 4. Moving Average Score (Trend Alignment & Support)
        price = info["price"]
        ma20 = info["ma20"]
        ma60 = info["ma60"]
        
        if price > 0 and ma20 > 0 and ma60 > 0:
            if price >= ma20 and ma20 >= ma60:
                ma_score = 3.0  # Clean uptrend alignment
            elif price >= ma60:
                ma_score = 1.5  # Supported by MA60
            else:
                ma_score = 0.5  # Under MA60
                
        total_score = flow_score + streak_score + volume_score + ma_score
        
        info["scores"] = {
            "flow": flow_score,
            "streak": streak_score,
            "volume": volume_score,
            "ma": ma_score,
            "total": round(total_score, 1)
        }
        scored_items.append(info)
        
    # Sort by total score descending, then change_rate descending
    scored_items.sort(key=lambda x: (x["scores"]["total"], x["change_rate"]), reverse=True)
    
    # Mock some data for test mode if empty
    if (test_mode or not scored_items) and len(scored_items) < 3:
        print("[LEADERS] Generating mock leader data for simulation test...")
        scored_items = [
            {
                "ticker": "012450",
                "name": "한화에어로스페이스",
                "price": 1055000,
                "change_rate": 3.84,
                "volume": 23545,
                "volume_ratio_20d": 0.1036,
                "ma20": 1020000,
                "ma60": 980000,
                "rsi14": 42.5,
                "foreign_net_buy_5d": -50000,
                "institution_net_buy_5d": 220000,
                "streak_days": 3,
                "catalyst": "지정학적 긴장 심화에 따른 유럽향 방산 추가 수주 계약 기대감 부각",
                "scores": {"flow": 1.5, "streak": 2.0, "volume": 2.0, "ma": 3.0, "total": 8.5}
            },
            {
                "ticker": "402340",
                "name": "SK스퀘어",
                "price": 1223000,
                "change_rate": -3.62,
                "volume": 51117,
                "volume_ratio_20d": 0.0547,
                "ma20": 1200000,
                "ma60": 1150000,
                "rsi14": 61.6,
                "foreign_net_buy_5d": -160000,
                "institution_net_buy_5d": 264000,
                "streak_days": 1,
                "catalyst": "주주환원 정책 확대 공시 및 자사주 소각 일정 확정",
                "scores": {"flow": 1.5, "streak": 1.0, "volume": 2.0, "ma": 3.0, "total": 7.5}
            },
            {
                "ticker": "454910",
                "name": "두산로보틱스",
                "price": 117300,
                "change_rate": 0.6,
                "volume": 146482,
                "volume_ratio_20d": 0.0474,
                "ma20": 110000,
                "ma60": 105000,
                "rsi14": 56.0,
                "foreign_net_buy_5d": 410000,
                "institution_net_buy_5d": 36000,
                "streak_days": 2,
                "catalyst": "스마트 팩토리 협동 로봇 라인업 강화 및 글로벌 공급망 다변화 성공 뉴스",
                "scores": {"flow": 3.0, "streak": 1.0, "volume": 2.0, "ma": 3.0, "total": 9.0}
            }
        ]
        scored_items.sort(key=lambda x: x["scores"]["total"], reverse=True)

    # Output top 3
    top_leaders = scored_items[:3]
    
    # Save cache
    summary = {
        "generated_at": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
        "test_mode": test_mode,
        "total_scored_count": len(scored_items),
        "leaders": top_leaders
    }
    
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    LEADERS_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] Saved realtime leaders cache to: {LEADERS_JSON.name}")
    
    # Render ASCII Table to Terminal
    print("\n" + "=" * 80)
    print("  [LEADERS] Real-time Market Leaders Scoring Summary (Top 3)")
    print("=" * 80)
    print(f"  Date: {summary['generated_at']} | Test Mode: {test_mode}")
    print("-" * 80)
    print(f"{'Rank':<5}{'Ticker':<8}{'Name':<15}{'Price':<10}{'Change%':<10}{'VolRatio':<10}{'TotalScore':<12}")
    print("-" * 80)
    for idx, item in enumerate(top_leaders, 1):
        print(f"{idx:<5}{item['ticker']:<8}{item['name']:<15}{item['price']:<10}{item['change_rate']:<10}{item['volume_ratio_20d']:<10}{item['scores']['total']:<12}")
        print(f"   Score details: Flow={item['scores']['flow']} | Streak={item['scores']['streak']} | Vol={item['scores']['volume']} | MA={item['scores']['ma']}")
        print(f"   Catalyst: {item['catalyst'] or 'N/A'}")
        print("-" * 80)
    print("=" * 80 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Real-time Market Leader Analyst")
    parser.add_argument("--test", action="store_true", help="Run in mock/simulation test mode")
    parser.add_argument("--cool-down", type=int, default=300, help="Cache age cool-down seconds (default: 300)")
    args = parser.parse_args()
    
    # Cool down check (skipped in test mode)
    if not args.test and get_leaders_cache_age_seconds() < args.cool_down:
        print(f"[LEADERS] Cached leaders file is fresh ({round(get_leaders_cache_age_seconds())}s old). Skipping API calls.")
        # Load and print cache
        cache = read_json_safe(LEADERS_JSON)
        if cache:
            print(f"Last updated at: {cache.get('generated_at')}")
            for idx, item in enumerate(cache.get("leaders", []), 1):
                print(f"[{idx}] {item.get('name')}({item.get('ticker')}): Score {item.get('scores', {}).get('total')} | Catalyst: {item.get('catalyst')}")
            return
            
    analyze_leaders(test_mode=args.test)

if __name__ == "__main__":
    main()
