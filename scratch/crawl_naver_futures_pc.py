import urllib.request
import json

def main():
    # Fetch FUT (futures) page and search for price patterns
    url = "https://finance.naver.com/sise/sise_index.naver?code=FUT"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://finance.naver.com/"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            html_content = res.read().decode('euc-kr', errors='replace')
            print("Fetch code=FUT Success!")
            
            # Find and print sections containing now_value, index, close, or similar keywords
            lines = html_content.splitlines()
            for idx, line in enumerate(lines):
                line_stripped = line.strip()
                if "now_value" in line or "now_val" in line or "time" in line or "iframe" in line or "aq_txt" in line or "sise_val" in line or "id=\"now_value\"" in line_stripped:
                    print(f"    Line {idx}: {line_stripped[:200]}")
    except Exception as e:
        print(f"Fetch failed: {e}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
