#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Morning Disclosure Blacklist Compiler (장전 공시 악재 블랙리스트 생성기)
Checks recent disclosures from Naver Finance and OpenDART API.
Blacklists tickers containing critical bad news keywords (e.g., litigation, embezzlement, paid-in capital increase).

Outputs:
- picks/cache/disclosure_blacklist.json
"""

import os
import re
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "picks" / "cache" / "disclosure_blacklist.json"
CORP_CODES_JSON = ROOT / "picks" / "cache" / "opendart_corp_codes.json"
KST = timezone(timedelta(hours=9))

TARGETS = {
    "066570": "LG전자",
    "046890": "서울반도체",
    "010170": "대한광통신"
}

BAD_KEYWORDS = [
    "불성실공시", "소송", "배임", "유상증자", "행정처분", "횡령",
    "의견거절", "부적정", "한정", "담보제공", "영업정지", "부도"
]

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def read_env_api_key() -> str:
    """Read OPENDART_API_KEY from env or .env.local file."""
    api_key = os.environ.get("OPENDART_API_KEY", "").strip()
    if api_key:
        return api_key
        
    env_local = ROOT / ".env.local"
    if env_local.exists():
        for line in env_local.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENDART_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""

def load_corp_code(ticker: str) -> str:
    """Load corp_code for target ticker from cache file."""
    if not CORP_CODES_JSON.exists():
        return ""
    try:
        data = json.loads(CORP_CODES_JSON.read_text(encoding="utf-8"))
        items = data.get("items", [])
        for item in items:
            if str(item.get("stock_code", "")).zfill(6) == ticker:
                return str(item.get("corp_code", ""))
    except Exception as e:
        print(f"WARN: Failed to parse corp codes cache: {e}")
    return ""

def fetch_naver_disclosures(ticker: str) -> list:
    """Scrape Naver Finance notices board for recent disclosures."""
    url = f"https://finance.naver.com/item/news_notice.naver?code={ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    events = []
    
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('cp949', errors='ignore')
            
            pattern = re.compile(
                r'<a[^>]*class="tit"[^>]*>([^<]+)</a>.*?<td[^>]*class="date"[^>]*>([^<]+)</td>',
                re.DOTALL
            )
            matches = pattern.findall(html)
            
            for title, date_str in matches:
                title = title.strip()
                date_match = re.match(r'^(\d{4})\.(\d{2})\.(\d{2})', date_str.strip())
                if date_match:
                    clean_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
                    events.append({
                        "title": title,
                        "date": clean_date,
                        "source": "Naver"
                    })
    except Exception as e:
        print(f"  [Naver Scrape Error] Ticker {ticker}: {e}", file=sys.stderr)
        
    return events

def fetch_opendart_disclosures(corp_code: str, api_key: str, bgn_de: str, end_de: str) -> list:
    """Fetch official KRX/DART disclosures from OpenDART API list.json."""
    if not corp_code or not api_key:
        return []
        
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": "100"
    }
    query = urllib.parse.urlencode(params)
    url = f"https://opendart.fss.or.kr/api/list.json?{query}"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode('utf-8'))
            if data.get("status") == "000":
                results = []
                for item in data.get("list", []):
                    # OpenDART returns date as YYYYMMDD
                    r_date = item.get("rcept_dt", "")
                    if len(r_date) == 8:
                        r_date = f"{r_date[:4]}-{r_date[4:6]}-{r_date[6:]}"
                    results.append({
                        "title": item.get("report_nm", ""),
                        "date": r_date,
                        "source": "OpenDART"
                    })
                return results
    except Exception as e:
        print(f"  [OpenDART API Error] Corp {corp_code}: {e}", file=sys.stderr)
        
    return []

def main() -> int:
    configure_stdio()
    print("=== [Morning Disclosure Compiler] Scanning for bad news disclosures ===")
    
    api_key = read_env_api_key()
    if api_key:
        print("OpenDART API Key detected.")
    else:
        print("OpenDART API Key NOT detected. Falling back to Naver Finance notice scraping only.")
        
    today_kst = datetime.now(KST)
    # Scan from 5 days ago to today to fully capture weekends/holidays
    bgn_de_date = today_kst - timedelta(days=5)
    bgn_de_str = bgn_de_date.strftime("%Y%m%d")
    end_de_str = today_kst.strftime("%Y%m%d")
    
    bgn_de_hyphen = bgn_de_date.strftime("%Y-%m-%d")
    end_de_hyphen = today_kst.strftime("%Y-%m-%d")
    
    print(f"Scanning range: {bgn_de_hyphen} to {end_de_hyphen}")
    
    blacklist = {}
    
    for ticker, name in TARGETS.items():
        print(f"Checking {name} ({ticker})...")
        disclosures = []
        
        # 1. Fetch Naver disclosures
        disclosures.extend(fetch_naver_disclosures(ticker))
        
        # 2. Fetch OpenDART disclosures (if API key and corp_code available)
        corp_code = load_corp_code(ticker)
        if corp_code and api_key:
            disclosures.extend(fetch_opendart_disclosures(corp_code, api_key, bgn_de_str, end_de_str))
            
        # Deduplicate disclosures by title and date
        unique_disc = {}
        for d in disclosures:
            key = (d["title"], d["date"])
            if key not in unique_disc:
                unique_disc[key] = d
                
        # 3. Filter for dates within our window and check keywords
        # Since Naver has dates without time, we check any notice from bgn_de_hyphen onwards
        bad_news_found = []
        for d in unique_disc.values():
            if d["date"] >= bgn_de_hyphen:
                for kw in BAD_KEYWORDS:
                    if kw in d["title"]:
                        bad_news_found.append({
                            "title": d["title"],
                            "date": d["date"],
                            "keyword": kw,
                            "source": d["source"]
                        })
                        break
                        
        if bad_news_found:
            print(f"  ⚠️ ALERT: Bad news disclosures found for {name} ({ticker})!")
            for item in bad_news_found:
                print(f"    - [{item['source']}] ({item['date']}) {item['title']} (Keyword: {item['keyword']})")
            blacklist[ticker] = {
                "name": name,
                "ticker": ticker,
                "blacklisted_at": today_kst.strftime("%Y-%m-%d %H:%M:%S"),
                "reasons": bad_news_found
            }
        else:
            print(f"  Clear. No bad disclosures found in date range.")
            
    # Save blacklist
    output_data = {
        "generated_at": today_kst.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_range": {
            "start": bgn_de_hyphen,
            "end": end_de_hyphen
        },
        "blacklist": blacklist
    }
    
    try:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write pattern
        tmp_file = OUTPUT_JSON.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_file.replace(OUTPUT_JSON)
        print(f"\n[OK] Saved disclosure blacklist to: {OUTPUT_JSON}")
        print(f"Total blacklisted tickers: {len(blacklist)}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to save disclosure blacklist: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
