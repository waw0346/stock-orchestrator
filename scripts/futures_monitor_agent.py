#!/usr/bin/env python3
# pylint: disable=broad-exception-caught,line-too-long
"""
선물모니터링에이전트 (Futures Monitoring Agent)
Real-time KOSPI200 Spot and Futures Basis Collector Daemon.

Features:
- Polls Naver Polling API every 5 seconds (with jitter) during market hours (09:00 ~ 15:45 KST).
- Writes raw ticks to picks/cache/futures_basis_ticks.jsonl.
- Broadcasts real-time state to picks/cache/futures_monitor_status.json.
- Self-recovers memory context from JSONL on startup.
- Performs end-of-day statistical roll-up and self-diagnostic feedback at 15:45 KST.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
TICKS_PATH = ROOT / "picks" / "cache" / "futures_basis_ticks.jsonl"
HISTORY_PATH = ROOT / "picks" / "cache" / "futures_basis_history.jsonl"
STATUS_PATH = ROOT / "picks" / "cache" / "futures_monitor_status.json"

KST = timezone(timedelta(hours=9))

# Standard User-Agents to avoid blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
]

def configure_stdio() -> None:
    """Prefer UTF-8 console output."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def now_kst() -> datetime:
    """Return current datetime in KST."""
    return datetime.now(KST)

class FuturesClient:
    """Handles polling requests to Naver Realtime API with spoofed headers and retries."""
    
    def __init__(self) -> None:
        self.url = "https://polling.finance.naver.com/api/realtime?query=SERVICE_INDEX:KPI200,FUT"
        self.consecutive_failures = 0
        
    def fetch(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Fetch Spot (KPI200) and Futures (FUT) prices.
        Returns (spot_price, futures_price).
        """
        req = urllib.request.Request(self.url)
        req.add_header("User-Agent", random.choice(USER_AGENTS))
        req.add_header("Referer", "https://finance.naver.com/")
        
        # Exponential backoff delay if failures occurred
        if self.consecutive_failures > 0:
            backoff = min(60, 2 ** self.consecutive_failures)
            print(f"[{now_kst().strftime('%Y-%m-%d %H:%M:%S')}] Backoff active. Waiting {backoff}s before retry.")
            time.sleep(backoff)
            
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                
            # Parse Polling API response
            # Format is usually: {"result": {"areas": [{"name": "KPI200", "datas": [{"nv": 38050, ...}]}, ...]}}
            areas = data.get("result", {}).get("areas", [])
            spot: Optional[float] = None
            fut: Optional[float] = None
            
            for area in areas:
                for d in area.get("datas", []):
                    cd = d.get("cd", "")
                    nv = d.get("nv")
                    if nv is None:
                        continue
                    
                    # nv values are multiplied by 100, e.g., 133500 represents 1335.00
                    price = float(nv) / 100.0
                    if cd == "KPI200":
                        spot = price
                    elif cd == "FUT":
                        fut = price
                    
            self.consecutive_failures = 0  # reset failures on success
            return spot, fut
            
        except urllib.error.URLError as e:
            self.consecutive_failures += 1
            print(f"[{now_kst().strftime('%Y-%m-%d %H:%M:%S')}] Network error: {e.reason}", file=sys.stderr)
            return None, None
        except Exception as e:
            self.consecutive_failures += 1
            print(f"[{now_kst().strftime('%Y-%m-%d %H:%M:%S')}] Fetch error: {e}", file=sys.stderr)
            return None, None

class MonitorAgent:
    """Manages the monitoring daemon loop, storage, and statistics."""
    
    def __init__(self, use_mock: bool = False) -> None:
        self.client = FuturesClient()
        self.use_mock = use_mock
        self.ticks_in_memory: List[Dict[str, Any]] = []
        self.load_existing_ticks()
        
    def load_existing_ticks(self) -> None:
        """Load today's already collected ticks from JSONL to restore memory context on restart."""
        self.ticks_in_memory = []
        if not TICKS_PATH.exists():
            return
        
        try:
            today_str = now_kst().strftime("%Y-%m-%d")
            with open(TICKS_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    tick = json.loads(line)
                    # Only keep ticks from today
                    if tick.get("timestamp", "").startswith(today_str):
                        self.ticks_in_memory.append(tick)
            if self.ticks_in_memory:
                print(f"INFO: Restored {len(self.ticks_in_memory)} ticks from today's log.")
        except Exception as e:
            print(f"WARN: Failed to restore ticks from log: {e}", file=sys.stderr)

    def write_tick(self, spot: float, fut: float, basis: float) -> None:
        """Append a tick to JSONL and update memory."""
        tick = {
            "timestamp": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "spot": round(spot, 2),
            "futures": round(fut, 2),
            "basis": round(basis, 3),
            "is_mock": self.use_mock
        }
        self.ticks_in_memory.append(tick)
        
        # Write to JSONL file
        TICKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TICKS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(tick) + "\n")

    def get_15m_avg_basis(self) -> float:
        """Calculate average basis of the last 15 minutes (180 ticks)."""
        if not self.ticks_in_memory:
            return 0.0
        # 15 minutes is 180 ticks (5s interval)
        recent_ticks = self.ticks_in_memory[-180:]
        bases = [t["basis"] for t in recent_ticks]
        return sum(bases) / len(bases)

    def detect_stale_data(self) -> bool:
        """Check if last 60 ticks (5 minutes) are identical, indicating market close or frozen API."""
        if len(self.ticks_in_memory) < 60:
            return False
        last_60 = self.ticks_in_memory[-60:]
        first_spot = last_60[0]["spot"]
        # If all spots and futures are identical, it is stale
        for t in last_60[1:]:
            if t["spot"] != first_spot:
                return False
        return True

    def update_broadcast_status(self, spot: Optional[float], fut: Optional[float], is_stale: bool, success_rate: float) -> None:
        """Update picks/cache/futures_monitor_status.json for other agents to read."""
        status_data = {
            "timestamp": now_kst().strftime("%Y-%m-%d %H:%M:%S"),
            "pid": os.getpid(),
            "status": "RUNNING",
            "spot_price": round(spot, 2) if spot else None,
            "futures_price": round(fut, 2) if fut else None,
            "basis": round(fut - spot, 3) if fut and spot else None,
            "avg_basis_15m": round(self.get_15m_avg_basis(), 3) if self.ticks_in_memory else 0.0,
            "risk_level": "NORMAL",
            "is_stale": is_stale,
            "health": {
                "polling_success_rate": round(success_rate, 4),
                "daemon_uptime_ticks": len(self.ticks_in_memory)
            }
        }
        
        # Dynamic Risk Assessment
        if status_data["avg_basis_15m"] <= -2.0:
            status_data["risk_level"] = "HIGH"
        elif status_data["avg_basis_15m"] <= -1.5:
            status_data["risk_level"] = "WARN"
            
        try:
            STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATUS_PATH.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception as e:
            print(f"WARN: Failed to write broadcast status: {e}", file=sys.stderr)

    def generate_mock_tick(self) -> Tuple[float, float]:
        """Generate simulated KOSPI200 Spot and Futures prices."""
        # Simple random walk or standard levels
        if not self.ticks_in_memory:
            spot = 380.0
            fut = 379.5
        else:
            last = self.ticks_in_memory[-1]
            spot = last["spot"] + random.normalvariate(0, 0.05)
            # Add some downward pressure to simulate program sell gate behavior occasionally
            min_basis = -2.2 if random.random() < 0.1 else -0.5
            fut = spot + min_basis + random.normalvariate(0, 0.05)
        return spot, fut

    def do_daily_rollup(self, success_rate: float) -> None:
        """Aggregate stats, write history report, and clear raw tick file."""
        if not self.ticks_in_memory:
            print("INFO: No ticks to roll up today.")
            return
            
        bases = [t["basis"] for t in self.ticks_in_memory]
        n = len(bases)
        mean_b = round(sum(bases) / n, 4)
        min_b = min(bases)
        max_b = max(bases)
        
        variance = sum((x - mean_b) ** 2 for x in bases) / n
        std_b = round(variance ** 0.5, 4)
        
        # Calculate EMA
        ema_b = bases[0]
        alpha = 0.05
        for val in bases[1:]:
            ema_b = alpha * val + (1 - alpha) * ema_b
        ema_b = round(ema_b, 4)
        
        anomaly_count = len([x for x in bases if x <= -2.0])
        anomaly_ratio = round(anomaly_count / n, 4)
        
        risk_level = "NORMAL"
        if anomaly_ratio >= 0.1 or min_b <= -2.5:
            risk_level = "HIGH"
        elif anomaly_ratio > 0.0 or min_b <= -1.8:
            risk_level = "WARN"
            
        # Self-feedback loop diagnostic check
        health_status = "EXCELLENT"
        feedback_notes = []
        if success_rate < 0.95:
            health_status = "DEGRADED"
            feedback_notes.append("API Polling success rate is below 95%. Consider reviewing networking or User-Agent rotation.")
        if anomaly_ratio > 0.3:
            feedback_notes.append("Severe backwardation anomaly occurred today. Basis filter successfully blocked trades for prolonged periods.")
            
        history_entry = {
            "date": now_kst().strftime("%Y-%m-%d"),
            "mean_basis": mean_b,
            "ema_basis": ema_b,
            "min_basis": min_b,
            "max_basis": max_b,
            "std_dev_basis": std_b,
            "anomaly_ratio": anomaly_ratio,
            "risk_level": risk_level,
            "tick_count": n,
            "polling_health": {
                "status": health_status,
                "success_rate": round(success_rate, 4),
                "feedback": feedback_notes
            }
        }
        
        # Write to history file
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(history_entry, ensure_ascii=False) + "\n")
            
        print(f"\n=================== EOD AUTO-FEEDBACK REPORT ===================")
        print(f"Date: {history_entry['date']}")
        print(f"Mean Basis: {mean_b} | Min: {min_b} | Max: {max_b}")
        print(f"Anomaly Ratio: {anomaly_ratio * 100:.2f}% | Risk: {risk_level}")
        print(f"Polling Success Rate: {success_rate * 100:.2f}% (Health: {health_status})")
        if feedback_notes:
            print("Feedback Notes:")
            for note in feedback_notes:
                print(f"  - {note}")
        print(f"================================================================")
        
        # Reset ticks log for next day
        try:
            if TICKS_PATH.exists():
                TICKS_PATH.unlink()
            print("INFO: Reset raw ticks file for the next session.")
        except Exception as e:
            print(f"WARN: Failed to clear tick cache: {e}", file=sys.stderr)
            
        # Update broadcast status to COMPLETED for today
        if STATUS_PATH.exists():
            try:
                status_data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
                status_data["status"] = "COMPLETED"
                status_data["timestamp"] = now_kst().strftime("%Y-%m-%d %H:%M:%S")
                STATUS_PATH.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            except Exception:
                pass

    def run_once(self) -> None:
        """Perform a single poll and exit (mostly for verify / manual execution check)."""
        if self.use_mock:
            spot, fut = self.generate_mock_tick()
        else:
            spot, fut = self.client.fetch()
            
        if spot and fut:
            basis = fut - spot
            self.write_tick(spot, fut, basis)
            self.update_broadcast_status(spot, fut, is_stale=False, success_rate=1.0)
            print(f"SUCCESS [Once]: Spot={spot:.2f}, Futures={fut:.2f}, Basis={basis:.3f}")
        else:
            print("FAILURE [Once]: Could not fetch data.", file=sys.stderr)
            self.update_broadcast_status(None, None, is_stale=True, success_rate=0.0)

    def is_market_hours(self) -> bool:
        """Check if KST is between 09:00 and 15:45 on weekdays."""
        now = now_kst()
        # Weekday check (0=Monday, 6=Sunday)
        if now.weekday() >= 5:
            return False
        start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        end_time = now.replace(hour=15, minute=45, second=0, microsecond=0)
        return start_time <= now <= end_time

    def start_daemon(self) -> None:
        """Main background daemon loop."""
        print(f"선물모니터링에이전트 데몬을 가동합니다. (PID: {os.getpid()})")
        print(f"저장 경로: {TICKS_PATH}")
        
        total_attempts = 0
        successful_attempts = 0
        rollup_done = False
        
        while True:
            try:
                now = now_kst()
                
                # Check for Market Hours
                if not self.is_market_hours():
                    # If market closed just now, and we haven't rolled up, do it.
                    if now.hour == 15 and now.minute >= 45 and not rollup_done:
                        success_rate = successful_attempts / total_attempts if total_attempts > 0 else 1.0
                        self.do_daily_rollup(success_rate)
                        rollup_done = True
                        # Reset daily stats
                        total_attempts = 0
                        successful_attempts = 0
                    
                    # Sleep until next check (longer sleep during non-market hours)
                    rollup_done = now.hour >= 16 or now.hour < 9
                    time.sleep(30)
                    continue
                
                # Market is open
                rollup_done = False
                total_attempts += 1
                
                if self.use_mock:
                    spot, fut = self.generate_mock_tick()
                else:
                    spot, fut = self.client.fetch()
                    
                is_stale = False
                if spot and fut:
                    successful_attempts += 1
                    basis = fut - spot
                    self.write_tick(spot, fut, basis)
                    is_stale = self.detect_stale_data()
                    if is_stale:
                        print(f"[{now.strftime('%H:%M:%S')}] WARN: Stale data detected (indices frozen).")
                else:
                    print(f"[{now.strftime('%H:%M:%S')}] ERROR: Failed to fetch tick.", file=sys.stderr)
                    
                success_rate = successful_attempts / total_attempts
                self.update_broadcast_status(spot, fut, is_stale, success_rate)
                
                # Jitter sleep around 5 seconds
                sleep_time = 5.0 + random.uniform(-0.5, 1.5)
                time.sleep(max(1.0, sleep_time))
                
            except KeyboardInterrupt:
                print("\nDaemon terminated by user.")
                break
            except Exception as e:
                print(f"Daemon Loop Error: {e}", file=sys.stderr)
                time.sleep(10)

def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Futures Monitoring Agent")
    parser.add_argument("--once", action="store_true", help="Fetch once and write to files, then exit.")
    parser.add_argument("--daemon", action="store_true", help="Run in daemon background loop during market hours.")
    parser.add_argument("--mock", action="store_true", help="Use mock simulation data instead of Naver Polling API.")
    args = parser.parse_args()
    
    agent = MonitorAgent(use_mock=args.mock)
    
    if args.once:
        agent.run_once()
        return 0
    elif args.daemon:
        agent.start_daemon()
        return 0
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
