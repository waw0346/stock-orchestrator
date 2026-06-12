import urllib.request
import json
import sys

def test_url(url):
    print(f"Testing URL: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
            print("  -> SUCCESS!")
            if isinstance(data, dict):
                # Print a small subset of keys
                keys = list(data.keys())
                print(f"  -> Keys: {keys}")
                # Print details of majors
                if "homeMajors" in data:
                    print("=== homeMajors ===")
                    for item in data["homeMajors"]:
                        print(f"  Item: {json.dumps(item, ensure_ascii=False)}")
                if "marketIndexInfos" in data:
                    print("=== marketIndexInfos ===")
                    for item in data["marketIndexInfos"]:
                        print(f"  Item: {json.dumps(item, ensure_ascii=False)}")
                # If there are items or basic fields, print them
                for k in ["closePrice", "nowVal", "price", "stockName", "itemName", "itemCode", "item"]:
                    if k in data:
                        print(f"    {k}: {data[k]}")
            elif isinstance(data, list):
                print(f"  -> List of size {len(data)}. First item:")
                if len(data) > 0:
                    print(f"    {list(data[0].keys())}")
                    # Print first 2 items basic info
                    for item in data[:3]:
                        print(f"    Item: {item.get('itemName') or item.get('stockName') or item.get('name')} -> {item.get('closePrice') or item.get('nowVal') or item.get('price')}")
    except Exception as e:
        print(f"  -> FAILED: {e}")

def main():
    # Test endpoints
    test_url("https://m.stock.naver.com/api/home/majors")
    test_url("https://m.stock.naver.com/api/index/.KS200/basic")
    test_url("https://m.stock.naver.com/api/index/KOSPI200/basic")
    test_url("https://m.stock.naver.com/api/index/KPI200/basic")
    test_url("https://m.stock.naver.com/api/index/.KOSPI200_F/basic")
    test_url("https://m.stock.naver.com/api/stock/KPI200/basic")
    # Test 101V9 (Sept 2026 Futures) and 101V6 (June 2026 Futures)
    test_url("https://m.stock.naver.com/api/stock/101V9/basic")
    test_url("https://m.stock.naver.com/api/stock/101V6/basic")
    test_url("https://m.stock.naver.com/api/index/101V9/basic")
    test_url("https://m.stock.naver.com/api/index/101V6/basic")

if __name__ == "__main__":
    main()
