#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DECA Cognitive Trigger Validator (실시간 뉴스 검증 및 최종 심사 스킬)
Queries Naver Finance mobile news API for a triggered ticker.
Applies the 6-Hour News Time Guard to filter out stale news.
Scans for bad news keywords to output a PASS/BLOCK decision.

Usage:
- python scripts/check_deca_trigger.py
- python scripts/check_deca_trigger.py --ticker 066570
"""

import os
import sys
import json
import argparse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRIGGER_JSON = ROOT / "picks" / "cache" / "deca_trigger.json"
KST = timezone(timedelta(hours=9))

# Bad news keywords for real-time news filter
BAD_NEWS_KEYWORDS = [
    "배임", "횡령", "소송", "의혹", "조사", "압수수색", "부도", "분쟁", "적자전환"
]

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def fetch_recent_news(ticker: str) -> list:
    url = f"https://m.stock.naver.com/api/news/stock/{ticker}?pageSize=20"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            if isinstance(data, list) and len(data) > 0:
                return data[0].get("items", [])
            return []
    except Exception as e:
        print(f"WARN: Failed to fetch news for {ticker}: {e}", file=sys.stderr)
        return []

def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Cognitive Trigger Validator")
    parser.add_argument("--ticker", help="Specific stock ticker to audit news for")
    args = parser.parse_args()
    
    ticker = ""
    name = ""
    trigger_price = 0
    
    # Check trigger file if ticker not provided
    if args.ticker:
        ticker = args.ticker.zfill(6)
        name = f"Ticker {ticker}"
    elif TRIGGER_JSON.exists():
        try:
            trigger_data = json.loads(TRIGGER_JSON.read_text(encoding="utf-8"))
            ticker = trigger_data.get("ticker", "").zfill(6)
            name = trigger_data.get("name", "")
            trigger_price = trigger_data.get("price", 0)
            print(f"Loaded trigger event from {TRIGGER_JSON}: {name} ({ticker}) at {trigger_price:,} KRW")
        except Exception as e:
            print(f"ERROR: Failed to parse trigger file: {e}", file=sys.stderr)
            return 1
    else:
        print("No active deca_trigger.json found and no --ticker provided. Standing by.")
        return 0
        
    print(f"\n=== [DECA Cognitive Auditor] Auditing {name} ({ticker}) ===")
    
    # 1. Fetch news
    news_items = fetch_recent_news(ticker)
    print(f"Fetched {len(news_items)} recent news stories.")
    
    now_kst = datetime.now(KST)
    six_hours_ago = now_kst - timedelta(hours=6)
    
    # 2. Filter news by 6-Hour Time Guard and search keywords
    recent_news = []
    bad_news_found = []
    
    for item in news_items:
        dt_str = item.get("datetime", "")
        if not dt_str or len(dt_str) != 12:
            continue
            
        try:
            news_dt = datetime.strptime(dt_str, "%Y%m%d%H%M").replace(tzinfo=KST)
        except ValueError:
            continue
            
        # 6-Hour News Time Guard
        if news_dt >= six_hours_ago:
            title = item.get("title", "")
            publisher = item.get("officeName", "")
            news_url = item.get("mobileNewsUrl", "")
            
            recent_news.append({
                "title": title,
                "publisher": publisher,
                "time": news_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "url": news_url
            })
            
            # Keyword audit
            for kw in BAD_NEWS_KEYWORDS:
                if kw in title:
                    bad_news_found.append({
                        "title": title,
                        "keyword": kw,
                        "time": news_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        "publisher": publisher
                    })
                    break
                    
    # 3. Output Decision
    print(f"\nNews within 6-hour guard (published since {six_hours_ago.strftime('%H:%M:%S')}): {len(recent_news)}")
    for n in recent_news:
        print(f"- [{n['publisher']}] {n['title']} ({n['time']})")
        
    decision = "PASS"
    reasons = []
    
    if bad_news_found:
        decision = "BLOCK"
        reasons = [f"Bad news keyword '{b['keyword']}' found in: {b['title']} ({b['publisher']})" for b in bad_news_found]
        
    print(f"\n=== Final Cognitive Decision: {decision} ===")
    if decision == "BLOCK":
        print("Reasons for BLOCK:")
        for r in reasons:
            print(f"  ❌ {r}")
    else:
        print("  ✅ No negative catalysts found. Position entry approved.")
        
    # Standardized output JSON for cross-AI portability
    audit_result = {
        "timestamp": now_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": ticker,
        "name": name,
        "decision": decision,
        "reasons": reasons,
        "audited_news_count": len(recent_news),
        "fresh_news_list": recent_news
    }
    
    # Save audit result next to trigger
    audit_file = ROOT / "picks" / "cache" / "deca_audit_result.json"
    try:
        tmp = audit_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(audit_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(audit_file)
        print(f"[OK] Saved audit results to: {audit_file}")
    except Exception as e:
        print(f"WARN: Failed to save audit results: {e}", file=sys.stderr)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
