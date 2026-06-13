import urllib.request
import json
import sys

def fetch_polling(query):
    url = f"https://polling.finance.naver.com/api/realtime?query={query}"
    print(f"Fetching: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('utf-8')
            data = json.loads(raw)
            print("SUCCESS!")
            # Pretty print the json data
            print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"FAILED: {e}")

def main():
    fetch_polling("SERVICE_INDEX:KPI200")
    fetch_polling("SERVICE_INDEX:FUT")

if __name__ == "__main__":
    main()
