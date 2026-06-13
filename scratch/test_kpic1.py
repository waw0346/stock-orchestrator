import urllib.request
import json

def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://m.stock.naver.com/"
    }
    
    urls = [
        "https://m.stock.naver.com/api/index/KPIc1/basic",
        "https://m.stock.naver.com/api/stock/KPIc1/basic",
        "https://m.stock.naver.com/api/index/0#KPIc1/basic",
        "https://m.stock.naver.com/api/stock/0#KPIc1/basic",
        "https://m.stock.naver.com/api/index/KOSPI200F/basic",
        "https://m.stock.naver.com/api/index/KOSPI200_F/basic",
        # Let's also check if Naver homeMajors had a reutersCode like YMcv1. What about KOSPI futures reutersCode?
        # Is there a KPIc1 in Naver's system? Let's check.
    ]
    
    for url in urls:
        print(f"Testing URL: {url}")
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=3) as res:
                data = json.loads(res.read().decode('utf-8'))
                print("  -> SUCCESS!")
                print(f"    Name: {data.get('stockName') or data.get('name')}")
                print(f"    Price: {data.get('closePrice') or data.get('nowVal')}")
                print(f"    ItemCode: {data.get('itemCode')}")
        except Exception as e:
            print(f"  -> FAILED: {e}")

if __name__ == "__main__":
    main()
