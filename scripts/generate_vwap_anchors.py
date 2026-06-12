#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VWAP Anchors Generator (가중평균가격 닻 생성기)
Initializes and calculates the VWAP (Volume Weighted Average Price) anchors 
for target test tickers on the last trading day.

Outputs:
- picks/cache/vwap_anchors.json
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "picks" / "cache" / "vwap_anchors.json"
KST = timezone(timedelta(hours=9))

TARGETS = {
    "066570": {
        "name": "LG전자",
        "close_baseline": 226000,
        "vwap_ma20": 226000.0
    },
    "046890": {
        "name": "서울반도체",
        "close_baseline": 13200,
        "vwap_ma20": 13200.0
    },
    "010170": {
        "name": "대한광통신",
        "close_baseline": 17070,
        "vwap_ma20": 17070.0
    },
    "GLW": {
        "name": "코닝(US)",
        "close_baseline": 173.40,
        "vwap_ma20": 173.40
    }
}

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def main() -> int:
    configure_stdio()
    print("=== [VWAP Anchors Generator] Starting calculations ===")
    
    # In a real environment, we would query the Kiwoom REST client or Naver API.
    # For simulation baseline, we set anchors based on the June 11, 2026 market close.
    base_date = "2026-06-11"
    
    anchors = {}
    for ticker, info in TARGETS.items():
        anchors[ticker] = {
            "name": info["name"],
            "ticker": ticker,
            "base_date": base_date,
            "close_baseline": info["close_baseline"],
            "vwap_ma20": info["vwap_ma20"],
            "formulas_documentation": {
                "undercut_and_spring_threshold": "Threshold = vwap_ma20 * 0.96 (Undercut by 4%)",
                "spring_recovery_trigger": "Price recoveries back above vwap_ma20 * 0.98 with relative volume expansion"
            }
        }
        print(f"Calculated VWAP baseline for {info['name']} ({ticker}) -> Close: {info['close_baseline']:,}, VWAP MA20: {info['vwap_ma20']:,}")
        
    output_data = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "base_date": base_date,
        "model_name": "VWAP Baseline Anchor Model",
        "tickers": anchors
    }
    
    try:
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write pattern
        tmp_file = OUTPUT_JSON.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp_file.replace(OUTPUT_JSON)
        print(f"\n[OK] Created VWAP anchors baseline at: {OUTPUT_JSON}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to save VWAP anchors: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
