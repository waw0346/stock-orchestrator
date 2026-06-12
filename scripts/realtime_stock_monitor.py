#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DECA Real-time Stock Monitor Engine (실시간 시세 감시 및 모의 매매 엔진)
Polls Naver Finance basic API every 5 seconds for target tickers.
Computes estimated Volume Power and U-shaped Relative Volume (RVOL).
Triggers Spring Recovery entries and manages virtual exit orders.

Usage:
- python scripts/realtime_stock_monitor.py
- python scripts/realtime_stock_monitor.py --mock
- python scripts/realtime_stock_monitor.py --rollback-trade <id>
- python scripts/realtime_stock_monitor.py --reset-ledger
"""

import os
import re
import sys
import csv
import json
import time
import argparse
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup paths and environment
ROOT = Path(__file__).resolve().parents[1]
LEDGER_CSV = ROOT / "picks" / "cache" / "simulation_ledger.csv"
TICK_LOG = ROOT / "picks" / "cache" / "monitor_ticks.jsonl"
STATUS_JSON = ROOT / "picks" / "cache" / "futures_monitor_status.json"
TRIGGER_JSON = ROOT / "picks" / "cache" / "deca_trigger.json"
BLACKLIST_JSON = ROOT / "picks" / "cache" / "disclosure_blacklist.json"
VOLUME_ANCHORS_JSON = ROOT / "picks" / "cache" / "volume_anchors.json"
VWAP_ANCHORS_JSON = ROOT / "picks" / "cache" / "vwap_anchors.json"

KST = timezone(timedelta(hours=9))

HEADERS = [
    "trade_id", "ticker", "name", "entry_time", "entry_price", 
    "exit_time", "exit_price", "exit_reason", "status", 
    "target_price", "stop_loss", "rvol", "volume_power", "profit_pct"
]

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def play_beep(freq: int, duration: int) -> None:
    """Play a beep alert on a separate non-blocking thread for cross-platform support."""
    def beep_thread():
        try:
            import winsound
            winsound.Beep(freq, duration)
        except ImportError:
            # Fallback for non-Windows or headless systems
            print("\a", end="", flush=True)
    threading.Thread(target=beep_thread, daemon=True).start()

def parse_env_file() -> dict:
    env_local = ROOT / ".env.local"
    env_data = {}
    if env_local.exists():
        for line in env_local.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env_data[k.strip()] = v.strip()
    return env_data

# Atomic file operations
def write_status(status: str, message: str) -> None:
    data = {
        "status": status,
        "message": message,
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        tmp = STATUS_JSON.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(STATUS_JSON)
    except Exception as e:
        print(f"WARN: Failed to write status file: {e}", file=sys.stderr)

# Ledger actions
def reset_ledger() -> int:
    try:
        LEDGER_CSV.parent.mkdir(parents=True, exist_ok=True)
        tmp = LEDGER_CSV.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
        tmp.replace(LEDGER_CSV)
        print("[OK] Reset simulation ledger successfully.")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to reset ledger: {e}", file=sys.stderr)
        return 1

def rollback_trade(trade_id: str) -> int:
    if not LEDGER_CSV.exists():
        print("ERROR: Ledger file does not exist.", file=sys.stderr)
        return 1
        
    try:
        rows = []
        found = False
        with open(LEDGER_CSV, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("trade_id") == trade_id:
                    found = True
                    continue
                rows.append(row)
                
        if not found:
            print(f"ERROR: Trade ID '{trade_id}' not found in the ledger.", file=sys.stderr)
            return 1
            
        tmp = LEDGER_CSV.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(LEDGER_CSV)
        print(f"[OK] Rolled back trade ID '{trade_id}' successfully.")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to rollback trade: {e}", file=sys.stderr)
        return 1

def get_ledger_positions() -> list:
    if not LEDGER_CSV.exists():
        return []
    try:
        rows = []
        with open(LEDGER_CSV, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows
    except Exception as e:
        print(f"WARN: Failed to read ledger: {e}", file=sys.stderr)
        return []

def save_ledger_positions(positions: list) -> None:
    try:
        tmp = LEDGER_CSV.with_suffix(".tmp")
        with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(positions)
        tmp.replace(LEDGER_CSV)
    except Exception as e:
        print(f"ERROR: Failed to save ledger: {e}", file=sys.stderr)

# Recover state from tick log
def recover_tick_history(today_str: str) -> dict:
    """
    Parse picks/cache/monitor_ticks.jsonl to recover Buy/Sell volumes in under 1 second.
    Returns: {ticker: {"buy_volume": X, "sell_volume": Y, "last_price": P, "last_volume": V, "last_dir": D}}
    """
    state = {}
    if not TICK_LOG.exists():
        return state
        
    print(f"Recovering tick history for date: {today_str}")
    try:
        with open(TICK_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tick = json.loads(line)
                    t_time = tick.get("time", "")
                    if not t_time.startswith(today_str):
                        continue
                        
                    ticker = tick.get("ticker", "")
                    price = tick.get("price")
                    vol = tick.get("volume")
                    
                    if ticker not in state:
                        state[ticker] = {
                            "buy_volume": 0,
                            "sell_volume": 0,
                            "last_price": price,
                            "last_volume": vol,
                            "last_dir": "BUY"
                        }
                        continue
                        
                    s = state[ticker]
                    last_price = s["last_price"]
                    last_vol = s["last_volume"]
                    
                    if vol > last_vol:
                        diff = vol - last_vol
                        if price > last_price:
                            s["buy_volume"] += diff
                            s["last_dir"] = "BUY"
                        elif price < last_price:
                            s["sell_volume"] += diff
                            s["last_dir"] = "SELL"
                        else:
                            # Unchanged price
                            if s["last_dir"] == "BUY":
                                s["buy_volume"] += diff
                            elif s["last_dir"] == "SELL":
                                s["sell_volume"] += diff
                            else:
                                s["buy_volume"] += diff // 2
                                s["sell_volume"] += diff - (diff // 2)
                                
                    s["last_price"] = price
                    s["last_volume"] = vol
                except Exception:
                    continue
        print(f"Recovery complete. Recovered state for {len(state)} tickers.")
    except Exception as e:
        print(f"WARN: Failed to parse tick log: {e}", file=sys.stderr)
        
    return state

# Expected Volume Calculation via interpolation
def get_expected_volume(anchors: dict, ticker: str, current_time: datetime) -> int:
    ticker_anchor = anchors.get(ticker)
    if not ticker_anchor:
        return 0
        
    time_slices = ticker_anchor.get("time_slices_15m", {})
    daily_avg = ticker_anchor.get("vol_avg20_daily", 500000)
    
    t_str = current_time.strftime("%H:%M")
    
    # Direct match
    if t_str in time_slices:
        return time_slices[t_str].get("expected_cum_vol", 0)
        
    # Sort slice times
    sorted_times = sorted(time_slices.keys())
    
    # Outside market hours
    if t_str < "09:00":
        return 0
    if t_str > "15:30":
        return daily_avg
        
    # Linear Interpolation
    t_prev = sorted_times[0]
    t_next = sorted_times[-1]
    
    for t in sorted_times:
        if t <= t_str:
            t_prev = t
        if t >= t_str:
            t_next = t
            break
            
    if t_prev == t_next:
        return time_slices[t_prev].get("expected_cum_vol", 0)
        
    # Interpolate ratios
    r_prev = time_slices[t_prev].get("ratio", 0.0)
    r_next = time_slices[t_next].get("ratio", 1.0)
    
    dt_curr = datetime.combine(datetime.today(), current_time.time())
    
    h_prev, m_prev = map(int, t_prev.split(":"))
    dt_prev = datetime.combine(datetime.today(), datetime.min.time().replace(hour=h_prev, minute=m_prev))
    
    h_next, m_next = map(int, t_next.split(":"))
    dt_next = datetime.combine(datetime.today(), datetime.min.time().replace(hour=h_next, minute=m_next))
    
    total_sec = (dt_next - dt_prev).total_seconds()
    elapsed_sec = (dt_curr - dt_prev).total_seconds()
    
    if total_sec <= 0:
        return int(daily_avg * r_prev)
        
    interp_ratio = r_prev + (r_next - r_prev) * (elapsed_sec / total_sec)
    return int(daily_avg * interp_ratio)

# Naver API quote fetcher
def fetch_naver_basic(ticker: str) -> dict:
    import ssl
    url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    
    def parse_polling_data(raw_data: dict) -> dict:
        try:
            areas = raw_data.get("result", {}).get("areas", [])
            if not areas:
                return {}
            datas = areas[0].get("datas", [])
            if not datas:
                return {}
            item = datas[0]
            return {
                "closePrice": str(item.get("nv", "0")),
                "accumulatedTradingVolume": str(item.get("aq", "0")),
                "stockName": item.get("nm", "")
            }
        except Exception as ex:
            raise ValueError(f"Failed to parse Naver Polling response: {ex}")

    try:
        # Try with default SSL verification first
        with urllib.request.urlopen(req, timeout=5) as res:
            raw = res.read().decode('cp949', errors='ignore')
            data = json.loads(raw)
            return parse_polling_data(data)
    except Exception as e:
        # Fallback to unverified SSL context (bypasses Windows certification verify errors)
        try:
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=5, context=context) as res:
                raw = res.read().decode('cp949', errors='ignore')
                data = json.loads(raw)
                return parse_polling_data(data)
        except Exception as e2:
            raise RuntimeError(f"Naver Polling API HTTP error: {e} (SSL fallback error: {e2})")



# Trigger event writer
def write_trigger_file(ticker: str, name: str, price: int, vwap: float, rvol: float, vp: float) -> None:
    data = {
        "timestamp": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
        "ticker": ticker,
        "name": name,
        "price": price,
        "vwap": vwap,
        "rvol": round(rvol, 3),
        "volume_power": round(vp, 1),
        "trigger_type": "Spring_Recovery"
    }
    try:
        tmp = TRIGGER_JSON.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(TRIGGER_JSON)
        print(f"\n[TRIGGER] Created trigger JSON at: {TRIGGER_JSON}")
    except Exception as e:
        print(f"WARN: Failed to write trigger file: {e}", file=sys.stderr)

# Mock tick sequences for LG전자 and 서울반도체
def get_mock_ticks() -> list:
    return [
        # LG전자 sequence: undercut -> spring recovery -> rise above target
        {"ticker": "066570", "time": "2026-06-12 09:05:00", "price": 226000, "volume": 100000},
        {"ticker": "066570", "time": "2026-06-12 09:15:00", "price": 220000, "volume": 200000}, # undercut (under 221,480)
        {"ticker": "066570", "time": "2026-06-12 09:30:00", "price": 219000, "volume": 300000},
        {"ticker": "066570", "time": "2026-06-12 09:45:00", "price": 224500, "volume": 3000000}, # spring recovery! (above 223,740), vol expand!
        {"ticker": "066570", "time": "2026-06-12 10:00:00", "price": 230000, "volume": 3200000},
        {"ticker": "066570", "time": "2026-06-12 10:15:00", "price": 243000, "volume": 3500000}, # target hit! (above 240,215)
        
        # 서울반도체 sequence: undercut -> spring recovery -> drop below stop loss
        {"ticker": "046890", "time": "2026-06-12 09:05:00", "price": 13200, "volume": 20000},
        {"ticker": "046890", "time": "2026-06-12 09:15:00", "price": 12800, "volume": 40000}, # undercut (under 12,936)
        {"ticker": "046890", "time": "2026-06-12 09:30:00", "price": 13100, "volume": 1500000}, # spring recovery! (above 13,068), vol expand!
        {"ticker": "046890", "time": "2026-06-12 09:45:00", "price": 12500, "volume": 1600000}, # stop loss hit! (under 12,576)
    ]

def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="DECA Real-time Stock Monitor")
    parser.add_argument("--mock", action="store_true", help="Run in mock simulation mode")
    parser.add_argument("--rollback-trade", help="Rollback specific trade ID in ledger")
    parser.add_argument("--reset-ledger", action="store_true", help="Reset simulation ledger")
    args = parser.parse_args()
    
    # CLI Command Actions
    if args.reset_ledger:
        return reset_ledger()
        
    if args.rollback_trade:
        return rollback_trade(args.rollback_trade)
        
    print("=== [DECA Real-time Stock Monitor Engine] Starting ===")
    
    # Validate Anchors Freshness
    if not VOLUME_ANCHORS_JSON.exists() or not VWAP_ANCHORS_JSON.exists():
        print("ERROR: Anchors files not found. Generate them first.", file=sys.stderr)
        return 1
        
    try:
        vol_data = json.loads(VOLUME_ANCHORS_JSON.read_text(encoding="utf-8"))
        vwap_data = json.loads(VWAP_ANCHORS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"ERROR: Failed to read anchors files: {e}", file=sys.stderr)
        return 1
        
    today_kst = datetime.now(KST)
    today_str = today_kst.strftime("%Y-%m-%d")
    
    # Strict Date Freshness Guard
    # VWAP baseline anchors must be from yesterday (the last trading day)
    # The last trading day should not be today before market open, or should be the D-1 trading day
    base_date = vwap_data.get("base_date", "")
    print(f"Loaded VWAP Anchors Base Date: {base_date}")
    
    # Skip date freshness check in mock mode
    if not args.mock:
        # Check if anchors base date is not today (it must be the last trading day D-1)
        if base_date == today_str:
            print("WARN: VWAP Anchors base date is today. It should be from the previous trading day (D-1).")
            
    # Load Blacklist
    blacklist = {}
    if BLACKLIST_JSON.exists():
        try:
            blacklist_data = json.loads(BLACKLIST_JSON.read_text(encoding="utf-8"))
            blacklist = blacklist_data.get("blacklist", {})
            print(f"Loaded blacklist. Blacklisted tickers: {list(blacklist.keys())}")
        except Exception as e:
            print(f"WARN: Failed to parse blacklist: {e}")
            
    # Initialize Watchlist and State
    targets = {
        "066570": "LG전자",
        "046890": "서울반도체",
        "010170": "대한광통신"
    }
    
    # Corning US correlation play
    glw_vwap = vwap_data.get("tickers", {}).get("GLW", {}).get("vwap_ma20", 173.4)
    glw_close = vwap_data.get("tickers", {}).get("GLW", {}).get("close_baseline", 173.4)
    glw_undercut = glw_close <= glw_vwap * 0.98
    print(f"Corning (GLW) undercut status: {glw_undercut} (Close: {glw_close}, VWAP: {glw_vwap})")
    
    # Ticker state memory
    ticker_states = {}
    
    # Recover state from tick log if live
    recovered_states = {}
    if not args.mock:
        recovered_states = recover_tick_history(today_str)
        
    for ticker, name in targets.items():
        rec = recovered_states.get(ticker, {})
        ticker_states[ticker] = {
            "name": name,
            "buy_volume": rec.get("buy_volume", 0),
            "sell_volume": rec.get("sell_volume", 0),
            "last_price": rec.get("last_price"),
            "last_volume": rec.get("last_volume"),
            "last_dir": rec.get("last_dir", "BUY"),
            "undercut": False
        }
        
    # Write initial run status
    write_status("RUNNING", "Real-time monitor loop is running.")
    
    failures = 0
    
    # MOCK MODE
    if args.mock:
        print("\n=== RUNNING MOCK SIMULATION (COMPRESSED TIME-SCALE) ===")
        mock_ticks = get_mock_ticks()
        
        for idx, tick in enumerate(mock_ticks):
            ticker = tick["ticker"]
            name = targets[ticker]
            price = tick["price"]
            volume = tick["volume"]
            tick_time_str = tick["time"]
            tick_time = datetime.strptime(tick_time_str, "%Y-%m-%d %H:%M:%S")
            
            s = ticker_states[ticker]
            last_price = s["last_price"]
            last_volume = s["last_volume"]
            
            # Estimate Volume Power (체결강도)
            if last_volume is not None and volume > last_volume:
                diff = volume - last_volume
                if price > last_price:
                    s["buy_volume"] += diff
                    s["last_dir"] = "BUY"
                elif price < last_price:
                    s["sell_volume"] += diff
                    s["last_dir"] = "SELL"
                else:
                    if s["last_dir"] == "BUY":
                        s["buy_volume"] += diff
                    elif s["last_dir"] == "SELL":
                        s["sell_volume"] += diff
                    else:
                        s["buy_volume"] += diff // 2
                        s["sell_volume"] += diff - (diff // 2)
                        
            vp = (s["buy_volume"] / s["sell_volume"]) * 100 if s["sell_volume"] > 0 else 100.0
            
            # RVOL
            expected_cum = get_expected_volume(vol_data.get("anchors", {}), ticker, tick_time)
            rvol = volume / expected_cum if expected_cum > 0 else 1.0
            
            s["last_price"] = price
            s["last_volume"] = volume
            
            print(f"[{tick_time_str}] MOCK TICK for {name} ({ticker}): Price: {price:,}, Vol: {volume:,}, RVOL: {rvol:.2f}, Vol Power: {vp:.1f}%")
            
            # Check Undercut / Spring Trigger
            vwap_ma20 = vwap_data.get("tickers", {}).get(ticker, {}).get("vwap_ma20", price)
            undercut_thresh = vwap_ma20 * 0.98
            spring_thresh = vwap_ma20 * 0.99
            
            if price <= undercut_thresh:
                if not s["undercut"]:
                    s["undercut"] = True
                    print(f"  📉 LG-style Undercut triggered for {name} (Price {price} <= Threshold {undercut_thresh:.0f})")
                    
            # Spring Recovery trigger
            # For 대한광통신 (010170), if Corning (GLW) is undercut, it can trigger spring recovery faster
            is_correlate = (ticker == "010170")
            trigger_condition = (s["undercut"] and price >= spring_thresh) or (is_correlate and glw_undercut and price >= vwap_ma20)
            
            if trigger_condition and rvol >= 1.5 and vp >= 105.0:
                print(f"  🔥 SPRING RECOVERY TRIGGERED for {name} ({ticker})!")
                # Reset undercut state
                s["undercut"] = False
                
                # Double-entry block check
                positions = get_ledger_positions()
                holding = [p for p in positions if p["ticker"] == ticker and p["status"] == "HOLDING"]
                
                if holding:
                    print(f"  Double-Entry Blocked: Already holding {name}.")
                else:
                    play_beep(2000, 800)
                    trade_id = f"TR_{ticker}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{idx}"
                    target_price = int(price * 1.07)
                    stop_loss = int(price * 0.96)
                    new_pos = {
                        "trade_id": trade_id,
                        "ticker": ticker,
                        "name": name,
                        "entry_time": tick_time_str,
                        "entry_price": price,
                        "exit_time": "",
                        "exit_price": "",
                        "exit_reason": "",
                        "status": "HOLDING",
                        "target_price": target_price,
                        "stop_loss": stop_loss,
                        "rvol": round(rvol, 3),
                        "volume_power": round(vp, 1),
                        "profit_pct": ""
                    }
                    positions.append(new_pos)
                    save_ledger_positions(positions)
                    write_trigger_file(ticker, name, price, vwap_ma20, rvol, vp)
                    print(f"  📝 Saved 가상 매수 to ledger: Entry Price {price:,}, Target {target_price:,}, Stop Loss {stop_loss:,}")
                    
            # Check Exit Conditions on Holding Positions
            positions = get_ledger_positions()
            for p in positions:
                if p["ticker"] == ticker and p["status"] == "HOLDING":
                    ent_price = int(p["entry_price"])
                    tar_price = int(p["target_price"])
                    sl_price = int(p["stop_loss"])
                    
                    if price >= tar_price:
                        # Target hit
                        p["status"] = "CLOSED"
                        p["exit_time"] = tick_time_str
                        p["exit_price"] = price
                        p["exit_reason"] = "TARGET"
                        p["profit_pct"] = round(((price - ent_price) / ent_price) * 100, 2)
                        play_beep(2500, 300)
                        play_beep(2500, 300)
                        print(f"  🚀 TARGET EXIT HIT for {name}: Exit Price {price:,} (+{p['profit_pct']}%)")
                        save_ledger_positions(positions)
                    elif price <= sl_price:
                        # Stop Loss hit
                        p["status"] = "CLOSED"
                        p["exit_time"] = tick_time_str
                        p["exit_price"] = price
                        p["exit_reason"] = "STOP_LOSS"
                        p["profit_pct"] = round(((price - ent_price) / ent_price) * 100, 2)
                        play_beep(1000, 1000)
                        print(f"  💥 STOP LOSS EXIT HIT for {name}: Exit Price {price:,} ({p['profit_pct']}%)")
                        save_ledger_positions(positions)
                        
            time.sleep(0.01) # Compressed time
            
        print("\n=== MOCK SIMULATION COMPLETE ===")
        return 0
        
    # LIVE SYSTEM RUN
    print("Running in live system monitoring mode.")
    
    try:
        while True:
            now_kst_dt = datetime.now(KST)
            t_now_str = now_kst_dt.strftime("%H:%M:%S")
            d_now_str = now_kst_dt.strftime("%Y-%m-%d")
            
            # Holiday Guard: Check weekend or market close
            # Weekend Check
            if now_kst_dt.weekday() in (5, 6):
                print(f"[{t_now_str}] Standby: Weekend (Saturday/Sunday).")
                write_status("STANDBY", "Market closed (Weekend).")
                time.sleep(60)
                continue
                
            # Early Cutoff Guard at 15:20 to save Naver rate limits for EOD scripts
            if now_kst_dt.time() >= datetime.strptime("15:20:00", "%H:%M:%S").time():
                print(f"[{t_now_str}] Cutoff reached (15:20 KST). Graceful shutdown to protect cron bandwidth.")
                write_status("COMPLETED", "Day monitoring completed at 15:20.")
                break
                
            # Market Hour Check
            if now_kst_dt.time() < datetime.strptime("09:00:00", "%H:%M:%S").time():
                print(f"[{t_now_str}] Standby: Pre-market hours.")
                write_status("STANDBY", "Market not open yet.")
                time.sleep(10)
                continue
                
            # Main Monitoring Logic
            for ticker, name in targets.items():
                # Check Blacklist
                if ticker in blacklist:
                    # Hard blocked due to bad disclosure
                    continue
                    
                s = ticker_states[ticker]
                
                try:
                    basic = fetch_naver_basic(ticker)
                    failures = 0 # reset failures
                    
                    price = int(str(basic.get("closePrice", "0")).replace(",", ""))
                    volume = int(str(basic.get("accumulatedTradingVolume", "0")).replace(",", ""))
                    
                    if price <= 0 or volume <= 0:
                        raise ValueError(f"Invalid price ({price}) or volume ({volume}) received.")
                        
                    # Extract last stats
                    last_price = s["last_price"]
                    last_volume = s["last_volume"]
                    
                    # Update tick estimation
                    if last_volume is not None and volume > last_volume:
                        diff = volume - last_volume
                        if price > last_price:
                            s["buy_volume"] += diff
                            s["last_dir"] = "BUY"
                        elif price < last_price:
                            s["sell_volume"] += diff
                            s["last_dir"] = "SELL"
                        else:
                            if s["last_dir"] == "BUY":
                                s["buy_volume"] += diff
                            elif s["last_dir"] == "SELL":
                                s["sell_volume"] += diff
                            else:
                                s["buy_volume"] += diff // 2
                                s["sell_volume"] += diff - (diff // 2)
                                
                        # Log tick to file
                        tick_data = {
                            "time": now_kst_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            "ticker": ticker,
                            "price": price,
                            "volume": volume
                        }
                        with open(TICK_LOG, "a", encoding="utf-8") as f:
                            f.write(json.dumps(tick_data) + "\n")
                            
                    vp = (s["buy_volume"] / s["sell_volume"]) * 100 if s["sell_volume"] > 0 else 100.0
                    
                    # Calculate RVOL
                    expected_cum = get_expected_volume(vol_data.get("anchors", {}), ticker, now_kst_dt)
                    rvol = volume / expected_cum if expected_cum > 0 else 1.0
                    
                    s["last_price"] = price
                    s["last_volume"] = volume
                    
                    # Log to console
                    print(f"[{t_now_str}] {name} ({ticker}) -> Price: {price:,}, RVOL: {rvol:.2f}, VP: {vp:.1f}%")
                    
                    # Undercut Spring Conditions check
                    vwap_ma20 = vwap_data.get("tickers", {}).get(ticker, {}).get("vwap_ma20", price)
                    undercut_thresh = vwap_ma20 * 0.98
                    spring_thresh = vwap_ma20 * 0.99
                    
                    if price <= undercut_thresh:
                        if not s["undercut"]:
                            s["undercut"] = True
                            print(f"  📉 Undercut: {name} fell below threshold {undercut_thresh:.0f}")
                            
                    # Trigger condition (undercut spring OR Corning US correlate for 대한광통신)
                    is_correlate = (ticker == "010170")
                    trigger_condition = (s["undercut"] and price >= spring_thresh) or (is_correlate and glw_undercut and price >= vwap_ma20)
                    
                    if trigger_condition and rvol >= 1.5 and vp >= 105.0:
                        print(f"  🚨 [TRIGGER] SPRING RECOVERY SIGNAL FOR {name} ({ticker})!")
                        s["undercut"] = False # Reset
                        
                        # Ledger double entry block
                        positions = get_ledger_positions()
                        holding = [p for p in positions if p["ticker"] == ticker and p["status"] == "HOLDING"]
                        
                        if not holding:
                            play_beep(2000, 800)
                            trade_id = f"TR_{ticker}_{now_kst_dt.strftime('%Y%m%d%H%M%S')}"
                            target_price = int(price * 1.07)
                            stop_loss = int(price * 0.96)
                            
                            new_pos = {
                                "trade_id": trade_id,
                                "ticker": ticker,
                                "name": name,
                                "entry_time": now_kst_dt.strftime("%Y-%m-%d %H:%M:%S"),
                                "entry_price": price,
                                "exit_time": "",
                                "exit_price": "",
                                "exit_reason": "",
                                "status": "HOLDING",
                                "target_price": target_price,
                                "stop_loss": stop_loss,
                                "rvol": round(rvol, 3),
                                "volume_power": round(vp, 1),
                                "profit_pct": ""
                            }
                            positions.append(new_pos)
                            save_ledger_positions(positions)
                            write_trigger_file(ticker, name, price, vwap_ma20, rvol, vp)
                            print(f"  📝 Recorded buy entry for {name} at {price:,}")
                            
                    # Monitor Exits
                    positions = get_ledger_positions()
                    changed = False
                    for p in positions:
                        if p["ticker"] == ticker and p["status"] == "HOLDING":
                            ent_price = int(p["entry_price"])
                            tar_price = int(p["target_price"])
                            sl_price = int(p["stop_loss"])
                            
                            if price >= tar_price:
                                p["status"] = "CLOSED"
                                p["exit_time"] = now_kst_dt.strftime("%Y-%m-%d %H:%M:%S")
                                p["exit_price"] = price
                                p["exit_reason"] = "TARGET"
                                p["profit_pct"] = round(((price - ent_price) / ent_price) * 100, 2)
                                play_beep(2500, 300)
                                play_beep(2500, 300)
                                print(f"  🚀 Profit Target Exited: {name} (+{p['profit_pct']}%)")
                                changed = True
                            elif price <= sl_price:
                                p["status"] = "CLOSED"
                                p["exit_time"] = now_kst_dt.strftime("%Y-%m-%d %H:%M:%S")
                                p["exit_price"] = price
                                p["exit_reason"] = "STOP_LOSS"
                                p["profit_pct"] = round(((price - ent_price) / ent_price) * 100, 2)
                                play_beep(1000, 1000)
                                print(f"  💥 Stop Loss Exited: {name} ({p['profit_pct']}%)")
                                changed = True
                                
                    if changed:
                        save_ledger_positions(positions)
                        
                except Exception as ex:
                    failures += 1
                    print(f"[{t_now_str}] Error polling {name} ({ticker}): {ex}", file=sys.stderr)
                    if failures >= 5:
                        print("🚨 PIPELINE FAILURE WATCHDOG: 5 consecutive failures. Switching to Standby.", file=sys.stderr)
                        write_status("ERROR", f"Pipeline failed 5 times consecutively. Last error: {ex}")
                        # 3 consecutive watchdog beeps
                        play_beep(1000, 300)
                        time.sleep(0.4)
                        play_beep(1000, 300)
                        time.sleep(0.4)
                        play_beep(1000, 300)
                        
                        # Pause for 10 minutes before retrying
                        time.sleep(600)
                        failures = 0
                        
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nEngine interrupted. Saving state and exiting...")
        write_status("STANDBY", "Engine stopped by user.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
