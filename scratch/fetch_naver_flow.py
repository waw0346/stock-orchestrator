import urllib.request
import re
import html
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
    for table_match in re.finditer(r"<table[^>]*>(.*?)</table>", html_content, flags=re.IGNORECASE | re.DOTALL):
        table_html = table_match.group(1)
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

def calculate_rsi(prices, period=14):
    if len(prices) <= period:
        return [50.0] * len(prices)
        
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    rsi_list = [50.0] # First element dummy
    
    # First average
    gains = [d if d > 0 else 0.0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0.0 for d in deltas[:period]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        rsi_list.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_list.append(100.0 - (100.0 / (1.0 + rs)))
        
    # Smoothed averages
    for d in deltas[period:]:
        gain = d if d > 0 else 0.0
        loss = -d if d < 0 else 0.0
        
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        
        if avg_loss == 0:
            rsi_list.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_list.append(100.0 - (100.0 / (1.0 + rs)))
            
    # Pad the beginning with 50.0 to match original list length
    result = [50.0] * (len(prices) - len(rsi_list)) + rsi_list
    return result

def main():
    ticker = "005930" # Samsung Electronics
    all_rows = []
    for page in range(1, 5): # Fetch 4 pages to have plenty of historical prices for RSI
        url = f"https://finance.naver.com/item/frgn.naver?code={ticker}&page={page}"
        try:
            html_content = request_text(url)
            page_rows = parse_frgn_page(html_content)
            all_rows.extend(page_rows)
        except Exception as e:
            break
            
    if not all_rows:
        print("데이터를 수집하지 못했습니다.")
        return 1
        
    all_rows.sort(key=lambda x: x["date"])
    
    # Calculate RSI
    prices = [r["close"] for r in all_rows]
    rsi_values = calculate_rsi(prices, 14)
    for idx, r in enumerate(all_rows):
        r["rsi"] = rsi_values[idx]
        
    # Print rows for the week of June 1 to June 5, 2026
    print("\n--- Daily Data with RSI (June 1 to June 5, 2026) ---")
    week_rows = [r for r in all_rows if "2026.06.01" <= r["date"] <= "2026.06.05"]
    for r in week_rows:
        print(f"Date: {r['date']} | Close: {r['close']:,} | RSI(14): {r['rsi']:.2f}")
        
    if week_rows:
        print(f"\n--- RSI on June 5, 2026 ---")
        print(f"RSI(14): {week_rows[-1]['rsi']:.2f}")

if __name__ == "__main__":
    main()
