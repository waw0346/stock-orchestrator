import urllib.request
import json
import urllib.parse
import sys

def test_search(keyword):
    encoded = urllib.parse.quote(keyword)
    url = f"https://m.stock.naver.com/api/search/stock?keyword={encoded}&page=1&pageSize=20"
    print(f"Searching for: {keyword} -> {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('utf-8')
            data = json.loads(raw)
            print("SUCCESS!")
            # Print items
            stocks = data.get("stocks", [])
            if stocks:
                for item in stocks:
                    print(f"  Name: {item.get('stockName')} -> Code: {item.get('itemCode')} / Ticker: {item.get('reutersCode')} / Type: {item.get('stockType')}")
            else:
                print(f"No stocks found. Raw: {raw[:300]}")
    except Exception as e:
        print(f"FAILED: {e}")

def main():
    test_search("코스피200선물")
    test_search("코스피200")
    test_search("선물")

if __name__ == "__main__":
    main()
