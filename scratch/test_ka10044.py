import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from kiwoom_rest_client import KiwoomRestClient, KiwoomSettings

def load_env():
    env_file = ROOT / ".env.local"
    if env_file.exists():
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

def main():
    load_env()
    settings = KiwoomSettings.from_env()
    client = KiwoomRestClient(settings)
    
    # Let's try to query ka10044 for today (2026-06-11)
    # Target values of org_tp: "0000", "9999", "0", "1000", etc.
    # Note: trade_type "2" = net buy
    date_str = "20260610"
    
    for org_tp in ["0000", "9999", "0", "1000", "3000", "7000"]:
        body = {
            "strt_dt": date_str,
            "end_dt": date_str,
            "mrkt_tp": "000",
            "org_tp": org_tp,
            "trde_tp": "2",
            "stex_tp": "1"
        }
        try:
            print(f"Testing org_tp: {org_tp}...")
            response = client.post_api("ka10044", "/api/dostk/mrkcond", body)
            items = response.get("daly_orgn_trde_stk") or response.get("items") or []
            print(f"-> Success! Got {len(items)} items")
            if items:
                print("  Top 3:")
                for item in items[:3]:
                    print(f"    {item.get('stk_cd')}: {item.get('stk_nm')} (netprps_qty: {item.get('netprps_qty')})")
        except Exception as e:
            print(f"-> Failed: {e}")

if __name__ == "__main__":
    main()
