import urllib.request
import json
import urllib.parse
import sys

def test_suggest(keyword):
    encoded = urllib.parse.quote(keyword)
    url = f"https://suggest-bar.daum.net/suggest?id=finance&category=all&limit=10&q={encoded}"
    print(f"Suggesting for: {keyword} -> {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://finance.daum.net/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('utf-8')
            data = json.loads(raw)
            print("SUCCESS!")
            # Print items
            items = data.get("items", [])
            for item in items:
                print(f"  {item}")
    except Exception as e:
        print(f"FAILED: {e}")

def main():
    test_suggest("코스피200선물")
    test_suggest("선물")

if __name__ == "__main__":
    main()
