import urllib.request
import json

urls_to_test = [
    ("comma_separated", "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KPI200,SERVICE_INDEX:FUT"),
    ("single_futs", "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:FUT"),
    ("pipe_separated", "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KPI200%7CSERVICE_INDEX:FUT"),
    ("comma_no_prefix", "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KPI200,FUT"),
    ("multiple_params", "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KPI200&query=SERVICE_INDEX:FUT"),
]

for label, url in urls_to_test:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    req.add_header("Referer", "https://finance.naver.com/")
    try:
        with urllib.request.urlopen(req, timeout=3) as response:
            body = response.read().decode("utf-8")
            data = json.loads(body)
            print(f"\n--- Test: {label} ---")
            areas = data.get("result", {}).get("areas", [])
            for area in areas:
                print(f"Area: {area.get('name')}")
                for d in area.get("datas", []):
                    print(f"  Code: {d.get('cd')}, Val: {d.get('nv')}")
    except Exception as e:
        print(f"[{label}] ERROR: {e}")
