#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mock test script to screen stocks with:
1. Foreigner or Institution continuous net buying (streak >= 3 days)
2. Current price is below the estimated average purchase price during the streak
3. Volume is increasing (volume expansion)
4. Outputs the findings to a markdown report.
"""

import os
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
INPUT_CSV = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
OUTPUT_MD = ROOT / "scratch" / "flow_avg_price_screener_report.md"

def parse_int(val):
    text = str(val or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0

def load_data(csv_path):
    if not csv_path.exists():
        print(f"ERROR: Input CSV not found at {csv_path}")
        return []
    
    rows = []
    with csv_path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = str(row.get("ticker", "")).strip().zfill(6)
            date = str(row.get("date", "")).strip()
            if not ticker.isdigit() or len(ticker) != 6 or not date:
                continue
            rows.append({
                "date": date,
                "ticker": ticker,
                "name": str(row.get("name") or ticker).strip(),
                "foreign_net_buy": parse_int(row.get("foreign_net_buy")),
                "institution_net_buy": parse_int(row.get("institution_net_buy")),
                "close": parse_int(row.get("close")),
                "volume": parse_int(row.get("volume")),
            })
    return rows

def get_streak_info(ticker_rows, flow_key):
    # Sort by date ascending
    ticker_rows = sorted(ticker_rows, key=lambda x: x["date"])
    
    # Calculate streak ending at the latest day
    streak = 0
    streak_rows = []
    for r in reversed(ticker_rows):
        if r[flow_key] <= 0:
            break
        streak += 1
        streak_rows.append(r)
    
    streak_rows.reverse()
    return streak, streak_rows

def main():
    print("=== Accumulating Stocks Screener Mock Test ===")
    print(f"Loading data from: {INPUT_CSV}")
    
    rows = load_data(INPUT_CSV)
    if not rows:
        print("No rows found. Exiting.")
        return 1
        
    by_ticker = defaultdict(list)
    for r in rows:
        by_ticker[r["ticker"]].append(r)
        
    candidates = []
    
    for ticker, ticker_rows in by_ticker.items():
        name = ticker_rows[0]["name"]
        
        # Test Foreigner streak
        f_streak, f_streak_rows = get_streak_info(ticker_rows, "foreign_net_buy")
        # Test Institution streak
        i_streak, i_streak_rows = get_streak_info(ticker_rows, "institution_net_buy")
        
        # We screen if either streak >= 3 days
        streaks_to_test = []
        if f_streak >= 3:
            streaks_to_test.append(("Foreigner", f_streak, f_streak_rows, "foreign_net_buy"))
        if i_streak >= 3:
            streaks_to_test.append(("Institution", i_streak, i_streak_rows, "institution_net_buy"))
            
        for buyer_type, streak_len, s_rows, net_buy_key in streaks_to_test:
            # Estimate average purchase price during the streak (VWAP of net buying)
            total_net_buy = sum(r[net_buy_key] for r in s_rows)
            if total_net_buy <= 0:
                continue
                
            weighted_price_sum = sum(r["close"] * r[net_buy_key] for r in s_rows)
            avg_purchase_price = weighted_price_sum / total_net_buy
            
            # Latest day info
            latest_row = ticker_rows[-1]
            latest_close = latest_row["close"]
            latest_volume = latest_row["volume"]
            
            # Yesterday info (for volume comparison and price direction)
            yesterday_row = ticker_rows[-2] if len(ticker_rows) >= 2 else None
            yesterday_close = yesterday_row["close"] if yesterday_row else latest_close
            yesterday_volume = yesterday_row["volume"] if yesterday_row else latest_volume
            
            # Conditions check:
            # 1. Price is below average purchase price
            is_below_avg = latest_close < avg_purchase_price
            price_diff_pct = ((avg_purchase_price - latest_close) / avg_purchase_price) * 100
            
            # 2. Price is rising from below (latest_close > yesterday_close, or latest close has stabilized)
            is_rising = latest_close > yesterday_close
            
            # 3. Volume is increasing (latest_volume > yesterday_volume)
            is_vol_expanding = latest_volume > yesterday_volume
            vol_increase_pct = ((latest_volume - yesterday_volume) / yesterday_volume * 100) if yesterday_volume > 0 else 0
            
            candidates.append({
                "ticker": ticker,
                "name": name,
                "buyer_type": buyer_type,
                "streak_len": streak_len,
                "total_net_buy": total_net_buy,
                "avg_purchase_price": avg_purchase_price,
                "latest_close": latest_close,
                "yesterday_close": yesterday_close,
                "latest_volume": latest_volume,
                "yesterday_volume": yesterday_volume,
                "is_below_avg": is_below_avg,
                "price_diff_pct": price_diff_pct,
                "is_rising": is_rising,
                "is_vol_expanding": is_vol_expanding,
                "vol_increase_pct": vol_increase_pct,
            })
            
    # Rank candidates: prioritize below average price + rising + volume expanding
    # Let's sort: (is_below_avg, is_vol_expanding, is_rising) descending, then streak_len descending
    candidates.sort(key=lambda x: (x["is_below_avg"], x["is_vol_expanding"], x["is_rising"], x["streak_len"]), reverse=True)
    
    # Generate Markdown Report
    lines = [
        "# 📊 수급 주체 평균매입단가 돌파 및 거래량 증가 종목 스크리닝 (모의 테스트)",
        f"**스크리닝 실행 시각**: {now_kst()} (KST)",
        f"**데이터 소스**: {INPUT_CSV.name} (최근 5거래일 스캔)",
        "",
        "본 리포트는 외국인 또는 기관이 **3일 이상 연속 순매수(매집)**하고 있는 종목 중에서, **현재 주가가 그들의 평균 매입 단가보다 낮거나 부근에 있으며(평균단가 밑에서 상승세)**, 동시에 **당일 거래량이 전일 대비 증가**하는 종목을 선별한 모의 테스트 결과입니다.",
        "",
        "---",
        "",
        "## 🎯 스크리닝 요약 테이블",
        "",
        "| 순위 | 종목명 (코드) | 수급 주체 | 연속 매집일 | 최근 종가 | 추정 평균단가 | 이격 비율 | 전일 종가 | 거래량 증가율 | 판정 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for idx, c in enumerate(candidates):
        rank = idx + 1
        ticker_str = f"[{c['name']} ({c['ticker']})](file:///{ROOT.as_posix()}/obsidian/stock_log/07_stock_analysis/{c['ticker']}_{c['name']}.md)"
        
        # Formatting prices
        close_str = f"{c['latest_close']:,}원"
        avg_str = f"{c['avg_purchase_price']:,.0f}원"
        diff_str = f"+{c['price_diff_pct']:.2f}% (하회)" if c['is_below_avg'] else f"-{-c['price_diff_pct']:.2f}% (상회)"
        yst_close_str = f"{c['yesterday_close']:,}원"
        vol_str = f"+{c['vol_increase_pct']:.1f}%" if c['is_vol_expanding'] else f"{c['vol_increase_pct']:.1f}%"
        
        # Decision logic
        decision = "🟢 PASS (조건 충족)"
        if not c['is_below_avg']:
            decision = "🟡 WATCH (평균단가 상회)"
        elif not c['is_vol_expanding']:
            decision = "🟡 WATCH (거래량 미증가)"
        
        if c['is_below_avg'] and c['is_vol_expanding'] and c['is_rising']:
            decision = "🔥 **EXCELLENT (골든타점)**"
            
        lines.append(
            f"| {rank} | {ticker_str} | {c['buyer_type']} | {c['streak_len']}일 | {close_str} | {avg_str} | {diff_str} | {yst_close_str} | {vol_str} | {decision} |"
        )
        
    lines.append("")
    lines.append("## 🔍 선정 기준 설명")
    lines.append("1. **연속 매집 (Streak)**: 최근 5거래일 중 최소 3일 연속으로 해당 주체의 순매수 수량이 양수(>0)인 종목.")
    lines.append("2. **추정 평균매입단가 (VWAP of Net Buy)**: 연속 매집 기간 동안의 `일별 순매수량 * 당일 종가` 누적 합을 `누적 순매수량`으로 나눈 거래량 가중 평균 단가.")
    lines.append("3. **평균단가 밑에서 상승 (Price Below & Rising)**: 현재가 < 추정 평균단가이면서, 당일 종가가 전일 종가보다 상승(`is_rising = True`).")
    lines.append("4. **거래량 증가 (Volume Expansion)**: 당일 거래량이 전일 거래량 대비 양의 증가율을 기록(`is_vol_expanding = True`).")
    lines.append("")
    lines.append("---")
    lines.append("*본 리포트는 모의 테스트 결과이며 실거래용 추천이 아닙니다.*")
    
    # Save file
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"Successfully generated report at: {OUTPUT_MD}")
    return 0

def now_kst():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    sys.exit(main())
