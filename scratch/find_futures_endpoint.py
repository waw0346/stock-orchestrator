import urllib.request
import json
import sys

def test_code(code):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }
    
    # Try index endpoint
    url_index = f"https://m.stock.naver.com/api/index/{code}/basic"
    try:
        req = urllib.request.Request(url_index, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as res:
            data = json.loads(res.read().decode('utf-8'))
            print(f"[INDEX] {code} -> SUCCESS! StockName: {data.get('stockName')}, Close: {data.get('closePrice')}")
            return ("index", code)
    except Exception:
        pass

    # Try stock endpoint
    url_stock = f"https://m.stock.naver.com/api/stock/{code}/basic"
    try:
        req = urllib.request.Request(url_stock, headers=headers)
        with urllib.request.urlopen(req, timeout=3) as res:
            data = json.loads(res.read().decode('utf-8'))
            print(f"[STOCK] {code} -> SUCCESS! StockName: {data.get('stockName') or data.get('name')}, Close: {data.get('closePrice') or data.get('nowVal')}")
            return ("stock", code)
    except Exception:
        pass
        
    return None

def main():
    candidate_codes = [
        "KPI200F", "KPI200_F", "KOSPI200F", "KOSPI200_F", "FUT_KOSPI200", "FUT_KPI200", 
        "K2FA001", "K2FA000", "KPI200", "KOSPI", "KOSDAQ",
        "101V9", "101V9000", "101V900", "101V0900", "101V09",
        "101U9", "101U9000", "101U6", "101U6000",
        "101V6", "101V6000",
        "KPI200F_C", "KPI200F_F"
    ]
    
    print("Starting KOSPI 200 Futures Code Search...")
    successes = []
    for code in candidate_codes:
        res = test_code(code)
        if res:
            successes.append(res)
            
    print(f"\nSearch complete. Found {len(successes)} successful codes.")

if __name__ == "__main__":
    main()
