#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculate VWAP accumulation (세력평균) for Samsung Biologics (207940) using Naver Finance.
"""

import urllib.request
import re
import html
import sys

# Fix console encoding on Windows for emoji printing
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def request_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Referer": "https://finance.naver.com/"
        }
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read()
        return raw.decode("cp949", errors="replace")

def clean_int(value: str) -> int:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    if not text:
        return 0
    try:
        return sign * int(float(text))
    except ValueError:
        return 0

def clean_abs_int(value: str) -> int:
    return abs(clean_int(value))

def find_correct_table(html_content: str) -> str:
    # Find all tables
    for table_match in re.finditer(r"<table[^>]*>(.*?)</table>", html_content, flags=re.IGNORECASE | re.DOTALL):
        table_html = table_match.group(1)
        # Check if we can parse enough rows starting with a valid date and having 8 cells
        rows_found = 0
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
            if len(cells) >= 8:
                cleaned_date = re.sub(r"<[^>]+>", "", html.unescape(cells[0])).strip()
                if re.match(r"^\d{4}\.\d{2}\.\d{2}$", cleaned_date):
                    rows_found += 1
        if rows_found >= 5:
            return table_html
    return ""

def parse_frgn_page(html_content: str) -> list:
    rows = []
    table_html = find_correct_table(html_content)
    if not table_html:
        return []
        
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.IGNORECASE | re.DOTALL):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.IGNORECASE | re.DOTALL)
        if len(cells) < 8:
            continue
        
        cleaned = [re.sub(r"<[^>]+>", "", html.unescape(cell)).strip() for cell in cells]
        if not re.match(r"^\d{4}\.\d{2}\.\d{2}$", cleaned[0]):
            continue
            
        date = cleaned[0]
        close = clean_abs_int(cleaned[1])
        volume = clean_abs_int(cleaned[4])
        institution = clean_int(cleaned[5])
        foreigner = clean_int(cleaned[6])
        
        rows.append({
            "date": date,
            "close": close,
            "volume": volume,
            "institution": institution,
            "foreigner": foreigner
        })
    return rows

def main():
    ticker = "207940"
    all_rows = []
    print("Naver Finance에서 삼성바이오로직스(207940) 투자자별 매매동향 데이터를 수집 중...")
    for page in range(1, 5):
        url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"
        try:
            html_content = request_text(url)
            page_rows = parse_frgn_page(html_content)
            all_rows.extend(page_rows)
            print(f"  페이지 {page} 수집 완료: {len(page_rows)}개 거래일 데이터")
        except Exception as e:
            print(f"  페이지 {page} 수집 실패: {e}")
            break
            
    if not all_rows:
        print("데이터를 수집하지 못했습니다.")
        return 1
        
    # Sort chronological ascending
    all_rows.sort(key=lambda x: x["date"])
    print(f"\n총 {len(all_rows)}거래일의 데이터가 성공적으로 정렬되었습니다 ({all_rows[0]['date']} ~ {all_rows[-1]['date']})")
    
    # Latest stock price
    latest = all_rows[-1]
    print(f"최근 기준 거래일: {latest['date']}")
    print(f"최근 종가: {latest['close']:,}원")
    print(f"최근 거래량: {latest['volume']:,}주\n")
    
    # 1. Streak calculation (consecutive net buy days going backwards)
    def calculate_streak(data, key):
        streak = 0
        streak_rows = []
        for r in reversed(data):
            if r[key] <= 0:
                break
            streak += 1
            streak_rows.append(r)
        streak_rows.reverse()
        return streak, streak_rows

    # 2. VWAP calculations
    def calculate_vwap(rows, key):
        if not rows:
            return 0.0, 0.0, 0.0, 0
            
        net_shares = sum(r[key] for r in rows)
        if net_shares == 0:
            return 0.0, 0.0, 0.0, 0
            
        abs_shares_sum = sum(abs(r[key]) for r in rows)
        if abs_shares_sum > 0:
            vwap = sum(r["close"] * abs(r[key]) for r in rows) / abs_shares_sum
        else:
            vwap = 0.0
            
        # Intensity VWAP
        intensity_sum = 0.0
        weighted_intensity_price = 0.0
        for r in rows:
            vol = r["volume"]
            net_buy = r[key]
            if vol > 0:
                weight = abs(net_buy) / vol
                intensity_sum += weight
                weighted_intensity_price += r["close"] * weight
        intensity_vwap = (weighted_intensity_price / intensity_sum) if intensity_sum > 0 else vwap
        
        # Value VWAP
        val_denom = sum(r["volume"] * abs(r[key]) for r in rows)
        value_vwap = sum(r["close"] * r["volume"] * abs(r[key]) for r in rows) / val_denom if val_denom > 0 else vwap
        
        return vwap, intensity_vwap, value_vwap, net_shares

    # Print results by investor type
    investors = [("외국인", "foreigner"), ("기관", "institution")]
    
    for name, key in investors:
        print(f"=== 👤 {name} 수급 & 평단가 분석 ===")
        
        # Streak (최근 연속 순매수)
        streak_len, streak_rows = calculate_streak(all_rows, key)
        if streak_len > 0:
            vwap, intensity, val_vwap, net_shares = calculate_vwap(streak_rows, key)
            print(f"▶ 최근 연속 순매수 기간: {streak_len}일 연속 ({streak_rows[0]['date']} ~ {streak_rows[-1]['date']})")
            print(f"  - 누적 순매수량: {net_shares:+,}주")
            print(f"  - 순매수 평단가 (Model 1, VWAP)      : {vwap:,.0f}원")
            print(f"  - 매집강도 평단가 (Model 2, Intensity) : {intensity:,.0f}원")
            print(f"  - 거래대금 평단가 (Model 3, Value)     : {val_vwap:,.0f}원")
        else:
            print(f"▶ 최근 연속 순매수 기간: 없음 (최근 거래일 순매도)")
            
        # Cumulative Fixed Periods
        periods = [5, 10, 20, 60]
        print("\n▶ 기간별 누적 평단가 및 순매매 현황:")
        print(f"  {'기간':<6} | {'누적 순매매량':<12} | {'누적 거래대금 (추정)':<15} | {'순매수 평단가':<10} | {'최종 판정':<10}")
        print("-" * 75)
        for p in periods:
            if len(all_rows) >= p:
                p_rows = all_rows[-p:]
                net_shares = sum(r[key] for r in p_rows)
                
                # Estimated net buy value (shares * close)
                net_value_krw = sum(r["close"] * r[key] for r in p_rows)
                net_value_billion = net_value_krw / 1_000_000_000.0
                
                # VWAP for positive buying days only (to get average buying price)
                buying_days = [r for r in p_rows if r[key] > 0]
                buying_shares = sum(r[key] for r in buying_days)
                if buying_shares > 0:
                    buy_vwap = sum(r["close"] * r[key] for r in buying_days) / buying_shares
                else:
                    buy_vwap = 0.0
                    
                # VWAP for negative selling days only (to get average selling price)
                selling_days = [r for r in p_rows if r[key] < 0]
                selling_shares = sum(abs(r[key]) for r in selling_days)
                if selling_shares > 0:
                    sell_vwap = sum(r["close"] * abs(r[key]) for r in selling_days) / selling_shares
                else:
                    sell_vwap = 0.0
                
                if net_shares > 0:
                    flow_type = "순매수"
                    avg_price = buy_vwap
                    flow_shares_str = f"{net_shares:+,}"
                    flow_val_str = f"{net_value_billion:+.2f}억원"
                elif net_shares < 0:
                    flow_type = "순매도"
                    avg_price = sell_vwap
                    flow_shares_str = f"{net_shares:+,}"
                    flow_val_str = f"{net_value_billion:+.2f}억원"
                else:
                    flow_type = "관망"
                    avg_price = 0.0
                    flow_shares_str = "0"
                    flow_val_str = "0.00억원"
                    
                price_str = f"{avg_price:,.0f}원" if avg_price > 0 else "-"
                print(f"  최근 {p:<2}일 | {flow_shares_str:>12} | {flow_val_str:>18} | {price_str:>12} | {flow_type:<5}")
        print("=" * 75 + "\n")
        
if __name__ == "__main__":
    main()
