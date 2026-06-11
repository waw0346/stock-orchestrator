import json
from pathlib import Path

def main():
    root = Path(r"c:\Users\kjw03\Desktop\stock orchestrator")
    history_path = root / "picks" / "cache" / "flow_comparison_history.json"
    
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    dates = ['2026-06-08', '2026-06-10', '2026-06-11']
    
    # For each date, let's get the foreigner and pension buy lists.
    # June 8 -> after_close
    # June 10 -> intraday
    # June 11 -> after_close
    
    buy_map = {}
    for d in dates:
        buy_map[d] = {}
        day_data = history[d]
        mode = "after_close" if "after_close" in day_data else "intraday"
        print(f"Date: {d} (using mode: {mode})")
        
        f_buy = {item["ticker"]: item["net_buy"] for item in day_data[mode].get("foreign_buy", []) if item["net_buy"] > 0}
        p_buy = {item["ticker"]: item["net_buy"] for item in day_data[mode].get("pension_buy", []) if item["net_buy"] > 0}
        
        buy_map[d]["foreign"] = f_buy
        buy_map[d]["pension"] = p_buy
        
    # Check 3-day consecutive foreigner buy
    f_streak = set(buy_map['2026-06-08']["foreign"].keys()) & \
               set(buy_map['2026-06-10']["foreign"].keys()) & \
               set(buy_map['2026-06-11']["foreign"].keys())
               
    print(f"\n3-day consecutive Foreigner buy: {f_streak}")
    
    # Check 3-day consecutive Pension buy
    p_streak = set(buy_map['2026-06-08']["pension"].keys()) & \
               set(buy_map['2026-06-10']["pension"].keys()) & \
               set(buy_map['2026-06-11']["pension"].keys())
               
    print(f"3-day consecutive Pension buy: {p_streak}")
    
    # Check overlap (both foreigners and pension funds bought on all 3 days)
    overlap = f_streak & p_streak
    print(f"Overlap: {overlap}")
    
    # Also check if any stock is bought by BOTH on each of the days (but not necessarily the same stock across 3 days)
    # i.e. daily overlaps
    for d in dates:
        both_bought = set(buy_map[d]["foreign"].keys()) & set(buy_map[d]["pension"].keys())
        print(f"Date {d} bought by both: {both_bought}")

if __name__ == "__main__":
    main()
