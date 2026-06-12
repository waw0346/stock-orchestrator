import urllib.request
import json
import sys

def test_url(url):
    print(f"Testing URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://finance.daum.net/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('utf-8')
            data = json.loads(raw)
            print("  -> SUCCESS!")
            if isinstance(data, dict):
                print(f"  -> Keys: {list(data.keys())[:10]}")
                for k in ["price", "tradePrice", "currentPrice", "name", "itemName", "symbolCode", "code"]:
                    if k in data:
                        print(f"    {k}: {data[k]}")
                # Print nested objects if interesting
                if "mainQuote" in data:
                    print(f"    mainQuote: {data['mainQuote']}")
            elif isinstance(data, list):
                print(f"  -> List of size {len(data)}. First item:")
                if len(data) > 0:
                    print(f"    {data[0]}")
    except Exception as e:
        print(f"  -> FAILED: {e}")

def main():
    # Candidates
    urls = [
        "https://finance.daum.net/api/domestic/futures",
        "https://finance.daum.net/api/domestic/futures/quotes",
        "https://finance.daum.net/api/quotes/KPIc1",
        "https://finance.daum.net/api/quotes/A101V9",
        "https://finance.daum.net/api/quotes/A101V900",
        "https://finance.daum.net/api/quotes/F_KPI200",
        "https://finance.daum.net/api/quotes/FUT_KPI200",
        # Let's also check if there is a general index/futures endpoint
        "https://finance.daum.net/api/domestic/futures/basic"
    ]
    for url in urls:
        test_url(url)

if __name__ == "__main__":
    main()
