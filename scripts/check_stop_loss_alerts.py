import os
import glob
import json
import argparse
import sys
from datetime import datetime

# Fix console encoding on Windows for emoji printing
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Simple frontmatter parser that handles key-value pairs
def parse_frontmatter(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    frontmatter = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    frontmatter[k] = v
    return frontmatter

def load_market_prices():
    snapshot_path = "picks/cache/market_data_snapshot.json"
    if not os.path.exists(snapshot_path):
        print(f"⚠️ Market data snapshot not found at {snapshot_path}")
        return {}
    
    try:
        with open(snapshot_path, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        
        price_map = {}
        for item in snapshot.get("items", []):
            ticker = item.get("ticker")
            price = item.get("price")
            if ticker and price is not None:
                price_map[ticker] = float(price)
        return price_map
    except Exception as e:
        print(f"❌ Error loading market snapshot: {e}")
        return {}

def log_alerts(issues_to_log):
    alerts_path = "picks/alerts/pending.json"
    
    # Load existing alerts
    if os.path.exists(alerts_path):
        try:
            with open(alerts_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"issues": []}
    else:
        data = {"issues": []}
    
    if "issues" not in data:
        data["issues"] = []
    
    existing_issues = data["issues"]
    newly_added = 0
    
    for issue in issues_to_log:
        # Check for duplicate: same ticker, type, and date
        duplicate = False
        for ex in existing_issues:
            if (ex.get("ticker") == issue.get("ticker") and 
                ex.get("type") == issue.get("type") and 
                ex.get("date") == issue.get("date")):
                duplicate = True
                break
        
        if not duplicate:
            existing_issues.append(issue)
            newly_added += 1
            
    if newly_added > 0:
        try:
            with open(alerts_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"✅ Logged {newly_added} new alerts to {alerts_path}")
        except Exception as e:
            print(f"❌ Failed to write alerts file: {e}")
    else:
        print("ℹ️ No new unique alerts to log (all already exist in alerts log).")

def main():
    parser = argparse.ArgumentParser(description="Monitor active/watch picks for stop-loss breaches.")
    parser.add_argument("--DryRun", action="store_true", help="Run in dry-run mode with simulated breaches.")
    parser.add_argument("--WriteAlerts", action="store_true", help="Actually write alerts to pending.json during dry-run.")
    args = parser.parse_args()
    
    print("=== Stop-Loss Alert Monitor ===")
    
    # 1. Load active/watch picks from picks/ directory
    pick_files = glob.glob("picks/*.md")
    active_picks = []
    
    for f in pick_files:
        basename = os.path.basename(f)
        if basename in ["INDEX.md", "WATCHLIST.md", "README.md", "README_v2.md", "CLAUDE.md", "CLAUDE_v2.md", "entry_exit_timing_playbook.md", "theme_report.md", "factor_scores.md", "disclosure_log.md"]:
            continue
        
        try:
            fm = parse_frontmatter(f)
            ticker = fm.get("ticker")
            status = fm.get("status")
            stop_loss = fm.get("stop_loss")
            name = fm.get("name")
            
            if ticker and status in ["active", "watch", "watch⚠️"] and stop_loss:
                active_picks.append({
                    "ticker": ticker,
                    "name": name,
                    "status": status,
                    "stop_loss": float(stop_loss),
                    "file": f
                })
        except Exception as e:
            print(f"⚠️ Failed to parse pick file {basename}: {e}")
            
    print(f"🔍 Found {len(active_picks)} active/watch picks to monitor.")
    
    # 2. Get current prices
    prices = load_market_prices()
    
    # 3. Simulate drop in DryRun mode
    if args.DryRun:
        print("\n[DryRun Mode Enabled] Simulating market drop...")
        # Artificially modify prices for demonstration:
        # Drop the first pick below stop_loss
        # Drop the second pick to be 1.5% above stop_loss (warning zone)
        if len(active_picks) > 0:
            p1 = active_picks[0]
            prices[p1["ticker"]] = p1["stop_loss"] - 1000.0
            print(f"  - Simulating breach for {p1['name']} ({p1['ticker']}): price={prices[p1['ticker']]:,.0f} <= stop_loss={p1['stop_loss']:,.0f}")
        if len(active_picks) > 1:
            p2 = active_picks[1]
            prices[p2["ticker"]] = p2["stop_loss"] * 1.015
            print(f"  - Simulating warning for {p2['name']} ({p2['ticker']}): price={prices[p2['ticker']]:,.0f} (within 3% of stop_loss={p2['stop_loss']:,.0f})")
            
    # 4. Check stop-loss breaches
    today_str = datetime.now().strftime("%Y-%m-%d")
    issues_detected = []
    
    for pick in active_picks:
        ticker = pick["ticker"]
        name = pick["name"]
        stop_loss = pick["stop_loss"]
        current_price = prices.get(ticker)
        
        if current_price is None:
            print(f"⚠️ No price available for {name} ({ticker})")
            continue
            
        # Stop-loss Breach
        if current_price <= stop_loss:
            msg = f"🚨 [Stop-Loss Breach] {name} ({ticker}) 현재가 {current_price:,.0f}원이 손절선 {stop_loss:,.0f}원을 이탈했습니다!"
            print(msg)
            issues_detected.append({
                "date": today_str,
                "ticker": ticker,
                "name": name,
                "type": "stop_loss_breach",
                "severity": "CRITICAL",
                "message": msg,
                "price": current_price,
                "stop_loss": stop_loss
            })
            
        # Warning Zone (within 3%)
        elif current_price <= stop_loss * 1.03:
            msg = f"⚠️ [Stop-Loss Warning] {name} ({ticker}) 현재가 {current_price:,.0f}원이 손절선 {stop_loss:,.0f}원에 근접했습니다 (이격 {((current_price - stop_loss)/stop_loss)*100:.2f}%)."
            print(msg)
            issues_detected.append({
                "date": today_str,
                "ticker": ticker,
                "name": name,
                "type": "stop_loss_warning",
                "severity": "WARN",
                "message": msg,
                "price": current_price,
                "stop_loss": stop_loss
            })
        else:
            print(f"✅ {name} ({ticker}) 현재가 {current_price:,.0f}원 (손절선 {stop_loss:,.0f}원 대비 +{((current_price - stop_loss)/stop_loss)*100:.1f}%) - 안전")

    # 5. Handle output / logging
    if issues_detected:
        if not args.DryRun or args.WriteAlerts:
            log_alerts(issues_detected)
        else:
            print(f"\n[DryRun] Would write {len(issues_detected)} alerts to pending.json, but did not write. (Pass --WriteAlerts to write)")
    else:
        print("\n🎉 No stop-loss breaches or warnings detected.")

if __name__ == "__main__":
    main()
