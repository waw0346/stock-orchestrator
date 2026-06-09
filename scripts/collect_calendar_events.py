import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta

# Setup encoding for clean terminal logs
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INDEX_PATH = os.path.join(PROJECT_ROOT, 'picks', 'INDEX.md')
VAULT_DIR = os.path.join(PROJECT_ROOT, 'obsidian', 'stock_log')
TEMPLATE_PATH = os.path.join(VAULT_DIR, '_templates', 'Stock Calendar Day Template.md')
HISTORY_PATH = os.path.join(VAULT_DIR, '11_calendar', 'sync_history.md')

def get_watchlist_stocks():
    print(f"Reading watchlist from: {INDEX_PATH}")
    stocks = []
    if not os.path.exists(INDEX_PATH):
        print("Error: picks/INDEX.md not found.")
        return stocks

    # Read INDEX.md which is written in UTF-8
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if not line.strip().startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 11 or parts[1] == '발행일' or parts[1].startswith('---'):
            continue

        ticker = parts[2]
        name = parts[3]
        raw_status = parts[9]
        
        # Clean status: remove emojis and spaces (e.g., "watch⚠️" -> "watch")
        status = re.sub(r'[^a-zA-Z]', '', raw_status).lower()

        if status in ['active', 'watch'] and re.match(r'^\d{6}$', ticker):
            stocks.append({
                "ticker": ticker,
                "name": name,
                "status": status
            })
            
    print(f"Found {len(stocks)} active/watch tickers.")
    return stocks

def fetch_naver_disclosures(ticker):
    """
    Fetch corporate disclosures directly from Naver Finance without external libs.
    Naver Finance is encoded in CP949 (EUC-KR).
    """
    url = f"https://finance.naver.com/item/news_notice.naver?code={ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    events = []
    
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            html = response.read().decode('cp949', errors='ignore')
            
            # regex pattern to match: <a href="..." class="tit">현금·현물배당결정</a> ... <td class="date">2026.04.15</td>
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
                        "date": clean_date
                    })
    except Exception as e:
        print(f"  Failed to scrape Naver disclosures for {ticker}: {str(e)}")
        
    return events

def update_calendar_file(date_str, row_entry, event_description):
    daily_cal_dir = os.path.join(VAULT_DIR, '11_calendar', 'daily')
    os.makedirs(daily_cal_dir, exist_ok=True)
    cal_file_path = os.path.join(daily_cal_dir, f"{date_str} Stock Calendar.md")

    if not os.path.exists(cal_file_path):
        if os.path.exists(TEMPLATE_PATH):
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as tf:
                tpl = tf.read()
            tpl_filled = tpl.replace('{{date}}', date_str)
            with open(cal_file_path, 'w', encoding='utf-8') as cf:
                cf.write(tpl_filled)
        else:
            with open(cal_file_path, 'w', encoding='utf-8') as cf:
                cf.write(f"---\ntitle: \"{date_str} Stock Calendar\"\ndate: \"{date_str}\"\ntype: stock-calendar-day\nstatus: active\n---\n\n# {date_str} Stock Calendar\n\n## 오늘 일정\n\n| 시간 | 분류 | 종목/시장 | 일정 | 중요도 | 상태 | 관련 노트 |\n|------|------|-----------|------|--------|------|-----------|\n")

    with open(cal_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Prevent duplicates
    if event_description in content:
        return False

    lines = content.split('\n')
    table_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and '일정' in line and '중요도' in line:
            table_index = i
            break

    if table_index != -1:
        sep_index = table_index + 1
        lines.insert(sep_index + 1, row_entry)
        new_content = '\n'.join(lines)
        with open(cal_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  Added event to calendar: {date_str} -> {event_description}")
        return True
    else:
        with open(cal_file_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{row_entry}\n")
        print(f"  Appended event to calendar: {date_str} -> {event_description}")
        return True

def log_sync_history(num_stocks, added_events, status_msg="성공"):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    
    if not os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
            f.write(f"---\ntitle: \"캘린더 동기화 이력\"\ntype: calendar-sync-history\nstatus: active\n---\n\n# 📅 캘린더 동기화 이력 (Calendar Sync History)\n\n| 실행 일시 | 대상 종목 수 | 추가된 일정 수 | 상태 |\n| --- | --- | --- | --- |\n")
            
    row = f"| {now_str} | {num_stocks} | {added_events} | {status_msg} |\n"
    
    with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    lines = content.split('\n')
    table_header_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('|') and '실행 일시' in line:
            table_header_idx = i
            break
            
    if table_header_idx != -1 and table_header_idx + 2 < len(lines):
        # Insert right below the separator (| --- | --- | ...)
        lines.insert(table_header_idx + 2, row.strip())
        new_content = '\n'.join(lines)
        with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
            f.write(new_content)
    else:
        with open(HISTORY_PATH, 'a', encoding='utf-8') as f:
            f.write(row)
            
    print(f"Logged sync history to: {HISTORY_PATH}")

def sync_events():
    stocks = get_watchlist_stocks()
    if not stocks:
        log_sync_history(0, 0, "종목 없음")
        return

    # Date range filters: current time metadata is 2026-06-09
    # We will use the system local date
    today = datetime.now()
    start_date = today - timedelta(days=30)
    end_date = today + timedelta(days=90)
    print(f"Syncing events between {start_date.strftime('%Y-%m-%d')} and {end_date.strftime('%Y-%m-%d')}")

    total_added = 0
    for stock in stocks:
        ticker = stock["ticker"]
        name = stock["name"]
        
        print(f"Scraping Naver disclosures for {name} ({ticker})...")
        disclosures = fetch_naver_disclosures(ticker)
        
        if not disclosures:
            print(f"  No recent disclosures found on Naver Finance for {name}.")
            continue
            
        # Parse and log matches
        for disc in disclosures:
            title = disc["title"]
            date_str = disc["date"]
            
            # Date range comparison
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue
                
            if not (start_date <= event_date <= end_date):
                continue
            
            classification = ""
            importance = "보통"
            
            if "배당" in title:
                classification = "배당일정"
                event_desc = f"현금/현물 배당 결정 공시 ({title})"
            elif "실적" in title or "매출" in title or "영업이익" in title:
                classification = "실적발표"
                importance = "높음"
                event_desc = f"영업실적 잠정 공시 ({title})"
            elif "주주총회" in title:
                classification = "공시/이벤트"
                event_desc = f"주주총회 소집결의 공시 ({title})"
            else:
                # Skip general/non-calendar disclosures to avoid bloating
                continue
                
            row = f"| 공시일 | {classification} | {name} ({ticker}) | {event_desc} | {importance} | active | [[07_stock_analysis/{ticker}_{name}]] |"
            is_added = update_calendar_file(date_str, row, f"{name} {event_desc}")
            if is_added:
                total_added += 1

    print(f"Stock Calendar synchronization completed. Total events handled: {total_added}")
    log_sync_history(len(stocks), total_added, "성공")

if __name__ == '__main__':
    sync_events()
