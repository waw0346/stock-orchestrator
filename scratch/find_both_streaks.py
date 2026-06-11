import json
from pathlib import Path

def main():
    root = Path(r"c:\Users\kjw03\Desktop\stock orchestrator")
    history_path = root / "picks" / "cache" / "flow_comparison_history.json"
    
    if not history_path.exists():
        print(f"File not found: {history_path}")
        return
        
    with open(history_path, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    print(f"Keys: {list(history.keys())}")
    for k, v in history.items():
        print(f"\nDate: {k}")
        for mode in v.keys():
            print(f"  Mode: {mode}")
            day_data = v[mode]
            print(f"    foreign_buy: {[x['name'] for x in day_data.get('foreign_buy', [])[:5]]}")
            print(f"    pension_buy: {[x['name'] for x in day_data.get('pension_buy', [])[:5]]}")

if __name__ == "__main__":
    main()
