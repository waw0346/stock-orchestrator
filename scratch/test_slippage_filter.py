import json
from pathlib import Path

def main():
    root = Path(r"c:\Users\kjw03\Desktop\stock orchestrator")
    market_path = root / "picks" / "cache" / "market_data_snapshot.json"
    candidate_path = root / "picks" / "cache" / "candidate_board.json"
    
    if not market_path.exists():
        print("Market snapshot cache not found.")
        return
        
    with open(market_path, "r", encoding="utf-8") as f:
        market_data = json.load(f)
        
    items = market_data.get("items", [])
    print(f"Total stocks in market universe: {len(items)}")
    
    blocked_by_liquidity = 0
    remaining_stocks = []
    
    # We will set a threshold of 5 billion KRW (5,000,000,000 KRW) for ADV/Daily trading value.
    liquidity_threshold = 5_000_000_000
    
    # Map ticker to trading value
    trading_values = {}
    
    for item in items:
        ticker = item.get("ticker", "")
        name = item.get("name", "")
        price = item.get("price")
        volume = item.get("volume")
        
        # Calculate daily trading value
        try:
            val = float(price) * float(volume)
        except (ValueError, TypeError):
            val = 0
            
        item["trading_value"] = val
        trading_values[ticker] = val
        
        if val < liquidity_threshold:
            blocked_by_liquidity += 1
        else:
            remaining_stocks.append(item)
            
    print(f"\n--- Liquidity Gate (ADV >= 5B KRW) Simulation ---")
    print(f"Blocked stocks: {blocked_by_liquidity} ({blocked_by_liquidity/len(items)*100:.2f}%)")
    print(f"Remaining stocks: {len(remaining_stocks)} ({len(remaining_stocks)/len(items)*100:.2f}%)")
    
    # Let's check candidate board filtering impact
    if candidate_path.exists():
        with open(candidate_path, "r", encoding="utf-8") as f:
            candidates = json.load(f)
        cand_items = candidates.get("rows", [])
        print(f"\nTotal candidates in candidate board: {len(cand_items)}")
        
        if not cand_items:
            print("Candidate board is empty.")
            return
            
        cand_blocked = 0
        cand_remaining = []
        for cand in cand_items:
            ticker = cand.get("ticker", "")
            # Find in items or calculation
            val = trading_values.get(ticker, 0)
            
            # If not found in market snapshot, check its own attributes if available
            if ticker not in trading_values:
                try:
                    price_val = cand.get("price") or 0
                    volume_val = cand.get("volume") or 0
                    val = float(price_val) * float(volume_val)
                except (ValueError, TypeError):
                    val = 0
            
            if val < liquidity_threshold:
                cand_blocked += 1
                print(f"  BLOCKED CANDIDATE: {cand['name']} ({ticker}) -> Est Value: {val/1e8:.2f}억 원")
            else:
                cand_remaining.append(cand)
                    
        print(f"\nCandidate Board Filtering Result:")
        print(f"  Blocked candidates: {cand_blocked} / {len(cand_items)} ({cand_blocked/len(cand_items)*100:.2f}%)")
        print(f"  Remaining candidates: {len(cand_remaining)}")

if __name__ == "__main__":
    main()
