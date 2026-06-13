#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
Volume Anchors Generator (가중평균거래량 닻 생성기)
Calculates historical volume baselines and implements the U-shaped Intraday Volume Model
to solve the "Morning Volume Trap" and isolate "Net Buying Volume" (순매수 거래량).

Outputs:
- picks/cache/volume_anchors.json
"""

import json
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
FLOW_HISTORY_CSV = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
MARKET_SNAPSHOT = ROOT / "picks" / "cache" / "market_data_snapshot.json"
OUTPUT_JSON = ROOT / "picks" / "cache" / "volume_anchors.json"

KST = timezone(timedelta(hours=9))

# Target test watchlist tickers
TARGETS = {
    "066570": "LG전자",
    "046890": "서울반도체",
    "010170": "대한광통신",
    "GLW": "코닝(US)"
}

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def parse_csv_history(csv_path: Path) -> Dict[str, List[int]]:
    """Parse historical volumes from foreign_flow_history.csv."""
    volumes = {}
    if not csv_path.exists():
        return volumes
        
    try:
        lines = csv_path.read_text(encoding="utf-8").splitlines()
        if not lines:
            return volumes
        headers = [h.strip() for h in lines[0].split(",")]
        ticker_idx = headers.index("ticker")
        vol_idx = headers.index("volume")
        
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) <= max(ticker_idx, vol_idx):
                continue
            ticker = parts[ticker_idx].zfill(6)
            try:
                vol = int(float(parts[vol_idx]))
                volumes.setdefault(ticker, []).append(vol)
            except ValueError:
                continue
    except Exception as e:
        print(f"WARN: Failed to parse CSV history: {e}", file=sys.stderr)
        
    return volumes

def load_market_data_snapshot(path: Path) -> Dict[str, int]:
    """Parse 20-day average volumes from market_data_snapshot.json technicals."""
    avg_vols = {}
    if not path.exists():
        return avg_vols
        
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items", [])
        for item in items:
            ticker = str(item.get("ticker", "")).zfill(6)
            tech = item.get("technical") or {}
            avg_20 = tech.get("volume_avg20") or tech.get("volume_ma20")
            if avg_20:
                avg_vols[ticker] = int(float(avg_20))
    except Exception as e:
        print(f"WARN: Failed to parse market snapshot: {e}", file=sys.stderr)
        
    return avg_vols

def calculate_expected_volume_ratio_at(t_kst: time) -> float:
    """
    U-shaped Intraday Volume Distribution Model (U자형 장중 거래량 분포 모델).
    Returns the expected cumulative fraction of the daily volume that should have occurred by t_kst.
    KOSPI/KOSDAQ market hours: 09:00 - 15:30 (6.5 hours / 390 minutes).
    
    U-shaped distribution weights:
    - 09:00 ~ 10:00 (60m): 40% of daily volume
    - 10:00 ~ 12:00 (120m): 20% of daily volume
    - 12:00 ~ 14:00 (120m): 15% of daily volume
    - 14:00 - 15:30 (90m): 25% of daily volume
    """
    # Define time constants
    market_start = time(9, 0)
    market_end = time(15, 30)
    
    if t_kst <= market_start:
        return 0.0
    if t_kst >= market_end:
        return 1.0
        
    # Convert time to minutes from start
    dt_now = datetime.combine(datetime.today(), t_kst)
    dt_start = datetime.combine(datetime.today(), market_start)
    elapsed_minutes = (dt_now - dt_start).total_seconds() / 60.0
    
    if elapsed_minutes <= 60.0:
        # First hour (09:00 - 10:00), 40% volume is distributed linearly
        return (elapsed_minutes / 60.0) * 0.40
        
    elif elapsed_minutes <= 180.0:
        # Midday morning (10:00 - 12:00), 20% volume
        added_minutes = elapsed_minutes - 60.0
        return 0.40 + (added_minutes / 120.0) * 0.20
        
    elif elapsed_minutes <= 300.0:
        # Midday afternoon (12:00 - 14:00), 15% volume
        added_minutes = elapsed_minutes - 180.0
        return 0.60 + (added_minutes / 120.0) * 0.15
        
    else:
        # Closing hours (14:00 - 15:30), 25% volume
        added_minutes = elapsed_minutes - 300.0
        return 0.75 + (added_minutes / 90.0) * 0.25

def main() -> int:
    configure_stdio()
    print("=== [Volume Anchors Generator] Starting calculations ===")
    
    # 1. Gather historical baseline volumes
    csv_history = parse_csv_history(FLOW_HISTORY_CSV)
    snapshot_history = load_market_data_snapshot(MARKET_SNAPSHOT)
    
    anchors = {}
    
    for ticker, name in TARGETS.items():
        daily_avg = 0
        
        # Priority 1: From technical indicators snapshot
        if ticker in snapshot_history:
            daily_avg = snapshot_history[ticker]
        # Priority 2: Calculate from CSV history if present
        elif ticker in csv_history and len(csv_history[ticker]) > 0:
            daily_avg = int(sum(csv_history[ticker]) / len(csv_history[ticker]))
        # Priority 3: Fallback hardcoded defaults if offline/fresh environment
        else:
            defaults = {
                "066570": 250000, # LG전자
                "046890": 450000, # 서울반도체
                "010170": 800000, # 대한광통신
                "GLW": 3200000    # 코닝
            }
            daily_avg = defaults.get(ticker, 500000)
            
        # 2. Build time-sliced expected cumulative volume anchors (every 15 minutes)
        time_slices = {}
        curr = datetime.combine(datetime.today(), time(9, 0))
        end = datetime.combine(datetime.today(), time(15, 30))
        
        while curr <= end:
            t_str = curr.strftime("%H:%M")
            ratio = calculate_expected_volume_ratio_at(curr.time())
            expected_cum_vol = int(daily_avg * ratio)
            time_slices[t_str] = {
                "ratio": round(ratio, 4),
                "expected_cum_vol": expected_cum_vol
            }
            curr += timedelta(minutes=15)
            
        anchors[ticker] = {
            "name": name,
            "ticker": ticker,
            "vol_avg20_daily": daily_avg,
            "time_slices_15m": time_slices,
            "formulas_documentation": {
                "relative_volume_by_time": "RVOL = Actual_Cumulative_Volume / Expected_Cumulative_Volume_At_T",
                "substantial_net_buy_volume": "Net_Buy_Vol = Cumulative_Volume * (Volume_Power_Strength - 100) / (Volume_Power_Strength + 100)",
                "substantial_net_buy_rvol": "Net_Buy_RVOL = Net_Buy_Vol / Expected_Cumulative_Volume_At_T"
            }
        }
        print(f"Calculated U-shaped volume baseline for {name} ({ticker}) -> Daily Avg: {daily_avg:,} shares")
        
    # 3. Write anchors to cache JSON
    output_data = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "model_name": "U-shaped Intraday Volume Model",
        "anchors": anchors
    }
    
    try:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n✅ Created volume anchors baseline at: {OUTPUT_JSON}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to save volume anchors: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
