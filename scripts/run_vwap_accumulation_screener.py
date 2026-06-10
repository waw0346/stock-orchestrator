#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Accumulating stock screener with advanced volume and value weighting models (VWAP)
combined with Moving Average Confluence scoring.
"""

import os
import csv
import json
import sys
import time
import argparse
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Fix console encoding on Windows for emoji printing
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_CSV = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
DEFAULT_OUTPUT_MD = ROOT / "obsidian" / "stock_log" / "04_candidate_boards" / "VWAP Accumulation Candidates.md"
DEFAULT_ANCHORS_JSON = ROOT / "picks" / "cache" / "flow_static_anchors.json"
KST = timezone(timedelta(hours=9))

sys.path.insert(0, str(ROOT / "scripts"))
try:
    from kiwoom_rest_client import KiwoomRestClient, KiwoomSettings, KiwoomRestError
except ImportError:
    class KiwoomRestError(RuntimeError):
        pass

def parse_int(val):
    text = str(val or "").strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0

def clean_int(value) -> int:
    """Parse Kiwoom signed numeric strings."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    if not text:
        return 0
    try:
        return sign * int(float(text))
    except ValueError:
        return 0

def clean_abs_int(value) -> int:
    """Parse a possibly signed price as an absolute integer."""
    return abs(clean_int(value))

def now_kst() -> str:
    """Return current KST datetime string."""
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

def standardize_flow_to_shares(net_buy: int, close_price: int, volume: int) -> int:
    """
    Standardize flow data (net_buy) to shares (수량) before calculations,
    preventing errors from mismatched share/value units.
    """
    if close_price <= 0:
        return 0
        
    abs_net_buy = abs(net_buy)
    if abs_net_buy == 0:
        return 0
        
    # Heuristic: If net_buy is larger than daily volume, it represents value (KRW) rather than shares
    if abs_net_buy > volume:
        shares_direct = abs_net_buy / close_price
        if shares_direct <= volume:
            return int(net_buy / close_price)
            
        shares_k = (abs_net_buy * 1000) / close_price
        if shares_k <= volume:
            return int((net_buy * 1000) / close_price)
            
        return int(net_buy / close_price)
        
    return int(net_buy)

def load_history(csv_path):
    if not csv_path.exists():
        print(f"⚠️ Input CSV not found at {csv_path}")
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
                "pension_net_buy": parse_int(row.get("pension_net_buy")),
                "close": parse_int(row.get("close")),
                "volume": parse_int(row.get("volume")),
            })
    return rows

def calculate_streak(ticker_rows, key):
    sorted_rows = sorted(ticker_rows, key=lambda x: x["date"])
    streak = 0
    streak_rows = []
    for r in reversed(sorted_rows):
        if r.get(key, 0) <= 0:
            break
        streak += 1
        streak_rows.append(r)
    streak_rows.reverse()
    return streak, streak_rows

class FakeKiwoomTransport:
    """Mock transport for opt10059 and opt10043 supporting 20 days of simulated history."""
    def __init__(self, rate_limit_threshold=10):
        self.request_count = 0
        self.rate_limit_threshold = rate_limit_threshold
        
    def __call__(self, url, body, headers, timeout):
        self.request_count += 1
        
        if self.request_count > self.rate_limit_threshold:
            raise KiwoomRestError("Rate limit exceeded (APILimitBanned)")
            
        ticker = body.get("stk_cd", "005930").zfill(6)
        
        # 20 trading days of simulated dates
        mock_dates = [
            "20260610", "20260609", "20260608", "20260607", "20260606",
            "20260605", "20260604", "20260603", "20260602", "20260601",
            "20260529", "20260528", "20260527", "20260526", "20260525",
            "20260522", "20260521", "20260520", "20260519", "20260518"
        ]
        
        base_price = 50000
        if ticker == "005930":
            base_price = 331000
        elif ticker == "000660":
            base_price = 2120000
        elif ticker == "402340":
            base_price = 1251000
            
        base_volume = 100000
        
        api_id = headers.get("api-id", "")
        if "opt10059" in url or api_id == "opt10059":
            items = []
            for idx, dt in enumerate(mock_dates):
                # Simulated price: decreasing slowly backwards (so today's price is highest)
                close = base_price - idx * 400
                volume = base_volume - idx * 2000
                
                # Mock Foreign, Institution and Pension Fund net buy values
                # Streak exists on recent 4 trading days (idx=1,2,3,4 since today idx=0 is skipped in D-1 mode)
                if idx in [1, 2, 3, 4]:
                    if ticker in ["005930", "402340"]:
                        f_val = 12000000 + idx * 1000000
                        i_val = -500000
                        p_val = 5000000 + idx * 200000
                    elif ticker == "000660":
                        f_val = -1000000
                        i_val = 8000000 + idx * 500000
                        p_val = 4000000 + idx * 300000
                    else:
                        f_val = 15000
                        i_val = 5000
                        p_val = 3000
                else:
                    f_val = -1000000
                    i_val = -500000
                    p_val = -200000
                    
                items.append({
                    "dt": dt,
                    "cur_prc": str(close),
                    "frgn_nt_buy_val": str(f_val),
                    "inst_nt_buy_val": str(i_val),
                    "pns_fd_nt_buy_val": str(p_val),
                    "trde_qty": str(volume)
                })
            return {
                "return_code": 0,
                "return_msg": "OK",
                "items": items
            }
            
        elif "opt10043" in url or api_id == "opt10043":
            items = []
            for idx, dt in enumerate(mock_dates):
                close = base_price - idx * 400
                volume = base_volume - idx * 2000
                items.append({
                    "dt": dt,
                    "cur_prc": str(close),
                    "trde_qty": str(volume)
                })
            return {
                "return_code": 0,
                "return_msg": "OK",
                "items": items
            }
            
        return {"return_code": 99, "return_msg": "Unknown API ID"}

def load_env_local():
    env = {}
    env_path = ROOT / ".env.local"
    if env_path.exists():
        try:
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip().strip('"').strip("'")
        except Exception as exc:
            print(f"Warning: Failed to read env file: {exc}")
    return env

def main():
    parser = argparse.ArgumentParser(description="Accumulating stock screener with advanced VWAP & MA Confluence weighting.")
    parser.add_argument("--live", action="store_true", help="Run live pipeline scan via Kiwoom REST API.")
    parser.add_argument("--test", action="store_true", help="Run offline simulation test of Kiwoom TR calls & rate limits.")
    parser.add_argument("--include-today", action="store_true", help="Include today's (incomplete) calendar date data.")
    parser.add_argument("--input-csv-path", default=str(DEFAULT_INPUT_CSV), help="Path to historical CSV data.")
    parser.add_argument("--output-md-path", default=str(DEFAULT_OUTPUT_MD), help="Path to output markdown report.")
    parser.add_argument("--anchors-json-path", default=str(DEFAULT_ANCHORS_JSON), help="Path to save static anchors JSON.")
    parser.add_argument("--top-prefilter", type=int, default=50, help="Number of active stocks to pre-filter before TR scan.")
    args = parser.parse_args()

    print("=== [VWAP Accumulation Screener] Starting analysis ===")
    
    input_csv = Path(args.input_csv_path)
    output_md = Path(args.output_md_path)
    anchors_json = Path(args.anchors_json_path)
    
    # 1. Load historical database
    history_rows = load_history(input_csv)
    history_by_ticker = defaultdict(list)
    ticker_names = {}
    for r in history_rows:
        history_by_ticker[r["ticker"]].append(r)
        ticker_names[r["ticker"]] = r["name"]
        
    print(f"Loaded {len(history_rows)} historical rows for {len(history_by_ticker)} tickers.")
    
    # 2. Exclude today's data by default (D-1 static anchor mode)
    today_str_hyphen = datetime.now(KST).strftime("%Y-%m-%d")
    today_str_flat = datetime.now(KST).strftime("%Y%m%d")
    if not args.include_today:
        print(f"D-1 Anchor Mode: Filtering out today's ({today_str_hyphen}) data from baseline calculations.")
        for ticker in list(history_by_ticker.keys()):
            filtered = [r for r in history_by_ticker[ticker] if r["date"] != today_str_hyphen]
            if filtered:
                history_by_ticker[ticker] = filtered
            else:
                del history_by_ticker[ticker]
                
    # Step 1: Pre-filtering
    prefilter_list = []
    for ticker, t_rows in history_by_ticker.items():
        t_rows = sorted(t_rows, key=lambda x: x["date"])
        latest = t_rows[-1]
        f_streak, _ = calculate_streak(t_rows, "foreign_net_buy")
        i_streak, _ = calculate_streak(t_rows, "institution_net_buy")
        p_streak, _ = calculate_streak(t_rows, "pension_net_buy")
        max_streak = max(f_streak, i_streak, p_streak)
        latest_vol = latest.get("volume", 0)
        prefilter_list.append((ticker, max_streak, latest_vol))
        
    prefilter_list.sort(key=lambda x: (x[1], x[2]), reverse=True)
    top_tickers = [x[0] for x in prefilter_list[:args.top_prefilter]]
    
    if not top_tickers:
        top_tickers = ["005930", "000660", "402340", "015760", "017670", "003490", "032640", "037560", "040300"]
        
    print(f"Pre-filtered {len(top_tickers)} target stocks for TR scan (top {args.top_prefilter}).")
    
    # 3. Step 2: Target TR scan (Live or Test Mode)
    analyzed_rows_by_ticker = {}
    
    if args.live or args.test:
        env = load_env_local()
        app_key = env.get("KIWOOM_APP_KEY") or os.environ.get("KIWOOM_APP_KEY", "")
        app_secret = env.get("KIWOOM_APP_SECRET") or os.environ.get("KIWOOM_APP_SECRET", "")
        access_token = env.get("KIWOOM_ACCESS_TOKEN") or os.environ.get("KIWOOM_ACCESS_TOKEN", "")
        base_url = env.get("KIWOOM_BASE_URL") or os.environ.get("KIWOOM_BASE_URL", "https://api.kiwoom.com")
        
        settings = KiwoomSettings(
            app_key=app_key,
            app_secret=app_secret,
            access_token=access_token,
            base_url=base_url,
            timeout=10
        )
        
        if args.test:
            transport = FakeKiwoomTransport(rate_limit_threshold=10)
            client = KiwoomRestClient(settings, transport=transport)
            print("Mode: TEST (Simulated Kiwoom REST OpenAPI responses and rate-limits)")
        else:
            client = KiwoomRestClient(settings)
            print("Mode: LIVE (Direct Kiwoom OpenAPI REST query)")
            
        for ticker in top_tickers:
            print(f"Scanning {ticker}...")
            try:
                body_59 = {
                    "stk_cd": ticker,
                    "dt": today_str_flat,
                    "amt_qty_tp": "1",
                    "trde_tp": "0"
                }
                res_59 = client.post_api("opt10059", "/api/dostk/opt10059", body_59)
                items_59 = res_59.get("items") or []
                
                body_43 = {
                    "stk_cd": ticker
                }
                res_43 = client.post_api("opt10043", "/api/dostk/opt10043", body_43)
                items_43 = res_43.get("items") or []
                
                price_vol_by_date = {}
                for item in items_43:
                    dt = str(item.get("dt", "")).strip().replace("-", "")
                    if not dt:
                        continue
                    price_vol_by_date[dt] = {
                        "close": clean_abs_int(item.get("cur_prc")),
                        "volume": clean_abs_int(item.get("trde_qty"))
                    }
                
                ticker_data = []
                for item in items_59:
                    dt = str(item.get("dt", "")).strip().replace("-", "")
                    if not dt:
                        continue
                    formatted_date = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}" if len(dt) == 8 else dt
                    
                    if not args.include_today and formatted_date == today_str_hyphen:
                        continue
                        
                    close_prc = clean_abs_int(item.get("cur_prc"))
                    volume_shares = clean_abs_int(item.get("trde_qty"))
                    
                    if dt in price_vol_by_date:
                        if close_prc == 0:
                            close_prc = price_vol_by_date[dt]["close"]
                        if volume_shares == 0:
                            volume_shares = price_vol_by_date[dt]["volume"]
                    
                    raw_f_val = clean_int(item.get("frgn_nt_buy_val"))
                    raw_i_val = clean_int(item.get("inst_nt_buy_val"))
                    raw_p_val = clean_int(item.get("pns_fd_nt_buy_val"))
                    
                    f_buy_shares = standardize_flow_to_shares(raw_f_val, close_prc, volume_shares)
                    i_buy_shares = standardize_flow_to_shares(raw_i_val, close_prc, volume_shares)
                    p_buy_shares = standardize_flow_to_shares(raw_p_val, close_prc, volume_shares)
                    
                    ticker_data.append({
                        "date": formatted_date,
                        "ticker": ticker,
                        "name": ticker_names.get(ticker, ticker),
                        "foreign_net_buy": f_buy_shares,
                        "institution_net_buy": i_buy_shares,
                        "pension_net_buy": p_buy_shares,
                        "close": close_prc,
                        "volume": volume_shares
                    })
                    
                if ticker_data:
                    analyzed_rows_by_ticker[ticker] = ticker_data
                    print(f"  [API] Standardized {len(ticker_data)} days for {ticker}")
                    
                if not args.test:
                    time.sleep(0.2)
                    
            except KiwoomRestError as exc:
                print(f"⚠️ [Rate Limit / API Error] Ticker {ticker} failed: {exc}. Falling back to CSV cache.")
                if ticker in history_by_ticker:
                    analyzed_rows_by_ticker[ticker] = history_by_ticker[ticker]
            except Exception as exc:
                print(f"⚠️ [Connection Error] Ticker {ticker} failed: {exc}. Falling back to CSV cache.")
                if ticker in history_by_ticker:
                    analyzed_rows_by_ticker[ticker] = history_by_ticker[ticker]
    else:
        print("Mode: OFFLINE (Using local CSV history cache database)")
        for ticker in top_tickers:
            if ticker in history_by_ticker:
                analyzed_rows_by_ticker[ticker] = history_by_ticker[ticker]

    # Load dynamic rules config for regime-based screening
    config_path = ROOT / "picks" / "cache" / "dynamic_rules_config.json"
    regime = "Risk-On"
    base_min_streak = 3
    is_risk_off = False
    if config_path.exists():
        try:
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
            regime = config_data.get("market_regime_decision", "Risk-On")
            base_min_streak = config_data.get("parameters", {}).get("flow_streak_consecutive_days", 3)
            is_risk_off = regime in ["Panic Risk-Off", "Correction/Neutral"]
            print(f"[Dynamic Rules] Loaded config: Regime={regime}, BaseMinStreak={base_min_streak}, IsRiskOff={is_risk_off}")
        except Exception as exc:
            print(f"Warning: Failed to load dynamic rules config: {exc}")

    # Define high-market-cap growth stock tickers (biotech, semiconductor, tech, high beta)
    GROWTH_STOCK_TICKERS = {
        "000660",  # SK하이닉스
        "011790",  # SKC
        "454910",  # 두산로보틱스
        "046890",  # 서울반도체
        "207940",  # 삼성바이오로직스
        "353200",  # 대덕전자
        "018260",  # 삼성SDS
        "007660",  # 이수페타시스
        "009150",  # 삼성전기
        "402340",  # SK스퀘어
        "012450",  # 한화에어로스페이스
        "217590",  # 티엠씨
        "077360",  # 덕산하이메탈
        "196170",  # 알테오젠
        "005930",  # 삼성전자
    }

    # 4. Standard Screener Calculations on Selected/Fallbacked Data
    candidates = []
    anchors_cache = {
        "generated_at": now_kst(),
        "base_date": today_str_hyphen if args.include_today else (
            sorted(list(set(r["date"] for rows in analyzed_rows_by_ticker.values() for r in rows)))[-1]
            if analyzed_rows_by_ticker else "N/A"
        ),
        "tickers": {}
    }
    
    for ticker, ticker_rows in analyzed_rows_by_ticker.items():
        name = ticker_rows[0]["name"]
        
        # Sort rows ascending by date
        ticker_rows = sorted(ticker_rows, key=lambda x: x["date"])
        latest = ticker_rows[-1]
        yesterday = ticker_rows[-2] if len(ticker_rows) >= 2 else None
        
        latest_close = latest["close"]
        latest_volume = latest["volume"]
        yesterday_close = yesterday["close"] if yesterday else latest_close
        yesterday_volume = yesterday["volume"] if yesterday else latest_volume
        
        # Calculate 20-day Simple Moving Average (MA20) of closing prices
        ma20 = sum(r["close"] for r in ticker_rows[-20:]) / len(ticker_rows[-20:])
        
        # Ensure everything analyzed is in standardized share format
        for r in ticker_rows:
            r["foreign_net_buy"] = standardize_flow_to_shares(r["foreign_net_buy"], r["close"], r["volume"])
            r["institution_net_buy"] = standardize_flow_to_shares(r["institution_net_buy"], r["close"], r["volume"])
            r["pension_net_buy"] = standardize_flow_to_shares(r.get("pension_net_buy", 0), r["close"], r["volume"])
            
        ticker_entry = {
            "name": name,
            "latest_close": latest_close,
            "ma20": round(ma20, 2),
            "buyers": {}
        }
        
        is_growth = ticker in GROWTH_STOCK_TICKERS
        required_streak = base_min_streak
        if is_growth and is_risk_off:
            required_streak += 1  # Add +1 day streak premium for growth stocks in Risk-Off
            
        for buyer, key in [("외국인", "foreign_net_buy"), ("기관", "institution_net_buy"), ("연기금", "pension_net_buy")]:
            streak_len, s_rows = calculate_streak(ticker_rows, key)
            if streak_len < required_streak:
                continue
                
            total_net_buy = sum(r[key] for r in s_rows)
            if total_net_buy <= 0:
                continue
                
            # Model 1: VWAP of Net Buy
            weighted_price_sum = sum(r["close"] * r[key] for r in s_rows)
            p_vwap = weighted_price_sum / total_net_buy
            
            # Model 2: Intensity-Weighted Average Price
            intensity_sum = 0.0
            weighted_intensity_price = 0.0
            for r in s_rows:
                vol = r["volume"]
                net_buy = r[key]
                if vol > 0:
                    weight = float(net_buy) / float(vol)
                    intensity_sum += weight
                    weighted_intensity_price += r["close"] * weight
            p_intensity = (weighted_intensity_price / intensity_sum) if intensity_sum > 0 else p_vwap
            
            # Model 3: Proxy Value VWAP
            val_denom = sum(r["volume"] * r[key] for r in s_rows)
            p_value_vwap = sum(r["close"] * r["volume"] * r[key] for r in s_rows) / val_denom if val_denom > 0 else p_vwap
            
            # Price relation to estimated average prices
            is_below_vwap = latest_close <= p_vwap
            is_below_intensity = latest_close <= p_intensity
            is_below_value_vwap = latest_close <= p_value_vwap
            
            is_rising = latest_close >= yesterday_close
            is_vol_expanding = latest_volume >= yesterday_volume
            vol_growth_pct = ((latest_volume - yesterday_volume) / yesterday_volume * 100.0) if yesterday_volume > 0 else 0.0
            
            # 📊 Calculate Moving Average Confluence Score (Out of 10 points)
            confluence_score = 0.0
            
            # 1. Gap between MA20 and VWAP (within 1.5% gives 2.5 points)
            ma20_vwap_gap = abs(ma20 - p_vwap) / ma20
            if ma20_vwap_gap <= 0.015:
                confluence_score += 2.5
            elif ma20_vwap_gap <= 0.03:
                confluence_score += 1.5
                
            # 2. Gap between MA20 and Intensity VWAP (within 1.5% gives 2.5 points)
            ma20_intensity_gap = abs(ma20 - p_intensity) / ma20
            if ma20_intensity_gap <= 0.015:
                confluence_score += 2.5
            elif ma20_intensity_gap <= 0.03:
                confluence_score += 1.5
                
            # 3. Price position: inside value zone (MA20 to min(VWAP, Intensity) - score 2.0)
            if latest_close <= max(ma20, p_vwap) and latest_close >= min(p_vwap, p_intensity) * 0.985:
                confluence_score += 2.0
                
            # 4. Price rebound recovery (score 1.5)
            if is_rising:
                confluence_score += 1.5
                
            # 5. Volume expansion (score 1.5)
            if is_vol_expanding:
                confluence_score += 1.5
                
            candidates.append({
                "ticker": ticker,
                "name": name,
                "buyer": buyer,
                "streak": streak_len,
                "latest_close": latest_close,
                "yesterday_close": yesterday_close,
                "latest_volume": latest_volume,
                "yesterday_volume": yesterday_volume,
                "p_vwap": p_vwap,
                "p_intensity": p_intensity,
                "p_value_vwap": p_value_vwap,
                "ma20": ma20,
                "is_below_vwap": is_below_vwap,
                "is_below_intensity": is_below_intensity,
                "is_below_value_vwap": is_below_value_vwap,
                "is_rising": is_rising,
                "is_vol_expanding": is_vol_expanding,
                "vol_growth_pct": vol_growth_pct,
                "confluence_score": confluence_score,
                "is_growth": is_growth,
                "is_risk_off": is_risk_off
            })
            
            ticker_entry["buyers"][buyer] = {
                "streak": streak_len,
                "p_vwap": round(p_vwap, 2),
                "p_intensity": round(p_intensity, 2),
                "p_value_vwap": round(p_value_vwap, 2),
                "confluence_score": round(confluence_score, 1)
            }
            
        if ticker_entry["buyers"]:
            anchors_cache["tickers"][ticker] = ticker_entry
            
    # Atomic write static anchors cache
    try:
        tmp_anchors_json = anchors_json.with_suffix(".json.tmp")
        tmp_anchors_json.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_anchors_json, "w", encoding="utf-8") as f:
            json.dump(anchors_cache, f, ensure_ascii=False, indent=2)
        if tmp_anchors_json.exists():
            if anchors_json.exists():
                os.remove(anchors_json)
            os.rename(tmp_anchors_json, anchors_json)
        print(f"✅ Atomically cached D-1 anchors with MA20 Confluence at: {anchors_json}")
    except Exception as exc:
        print(f"⚠️ Failed to write anchors JSON cache: {exc}")
        
    # Sort candidates by Confluence Score descending, then streak descending
    candidates.sort(key=lambda x: (x["confluence_score"], x["streak"]), reverse=True)
    
    # 5. Generate Obsidian Markdown Report
    lines = [
        "---",
        "title: \"가중 매집 평단가 및 이평선 컨플루언스 후보 보드\"",
        f"date: \"{today_str_hyphen}\"",
        "type: \"candidate-board\"",
        "status: \"active\"",
        "owner: \"obsi\"",
        "evidence_type: \"analysis\"",
        "tags:",
        "  - stock-orchestrator",
        "  - candidate-board",
        "  - vwap-confluence",
        "---",
        "",
        "# 📊 가중 매집 평단가 & 20일선 컨플루언스 후보 보드",
        f"**마지막 업데이트**: {now_kst()} (KST)",
        f"**대상 수급 이력**: {input_csv.name} (20거래일 분석 | D-1 고정 닻 적용)",
        "",
        "> [!NOTE] 수식 및 모델 설명",
        "> 1. **Model 1: 순매수 가중 평단가 (VWAP of Net Buy)** = `Sum(종가 * 순매수량) / Sum(순매수량)` — 순매수한 거래량 기준으로 매집 가격 추정.",
        "> 2. **Model 2: 매집 강도 가중 평단가 (Intensity-Weighted Price)** = `Sum(종가 * 매집비율) / Sum(매집비율)` — 전체 거래량 대비 순매집 비중이 큰 날에 가중치를 부여하여 추정.",
        "> 3. **Model 3: 거래대금 가중 평단가 (Value-Weighted Price)** = `Sum(종가 * 거래량 * 순매수량) / Sum(거래량 * 순매수량)` — 프록시 거래대금을 적용한 가중단가.",
        "> 4. **컨플루언스 점수 (Confluence Score)** = 10점 만점. 20일 이평선(MA20)과 세력평균단가(Model 1, 2)의 수렴 정도(이격률 1.5% 이내 시 가점), 주가의 밴드 진입 여부, 가격 반등(양봉), 거래량 확장을 종합 스코어링.",
        "",
        "---",
        "",
        "## 🎯 스크리닝 선정 후보군 (컨플루언스 점수 순)",
        "",
        "| 순위 | 종목명 (코드) | 수급 주체 | 연속 매집 | 최근 종가 | 20일선 (MA20) | Model 1 (VWAP) | Model 2 (Intensity) | 컨플루언스 점수 | 거래량 증가율 | 판정 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    
    for idx, c in enumerate(candidates):
        rank = idx + 1
        analysis_path = ROOT / "obsidian" / "stock_log" / "07_stock_analysis" / f"{c['ticker']}_{c['name']}.md"
        if analysis_path.exists():
            ticker_link = f"[[{c['ticker']}_{c['name']}|{c['name']}]]"
        else:
            ticker_link = f"{c['name']} ({c['ticker']})"
        
        close_str = f"{c['latest_close']:,}원"
        ma20_str = f"{c['ma20']:,.0f}원"
        vwap_str = f"{c['p_vwap']:,.0f}원"
        intensity_str = f"{c['p_intensity']:,.0f}원"
        score_str = f"**{c['confluence_score']:.1f} / 10.0**"
        
        vol_str = f"+{c['vol_growth_pct']:.1f}%" if c['vol_growth_pct'] > 0 else f"{c['vol_growth_pct']:.1f}%"
        
        # Determine Decision based on Confluence Score
        is_growth_stock = c.get('is_growth', False)
        is_risk_off_regime = c.get('is_risk_off', False)
        
        min_pass_score = 5.0
        min_excellent_score = 8.0
        if is_growth_stock and is_risk_off_regime:
            min_pass_score = 6.5
            min_excellent_score = 8.5
            
        if c['confluence_score'] >= min_excellent_score:
            decision = "🔥 **EXCELLENT (골든타점)**"
        elif c['confluence_score'] >= min_pass_score:
            decision = "🟢 **PASS (관심진입)**"
        else:
            decision = "🟡 **WATCH (관망)**"
            
        if is_growth_stock and is_risk_off_regime:
            decision += " <br>`⚠️ 성장주 보수적 기준 적용`"
            
        lines.append(
            f"| {rank} | {ticker_link} | {c['buyer']} | {c['streak']}일 | {close_str} | {ma20_str} | {vwap_str} | {intensity_str} | {score_str} | {vol_str} | {decision} |"
        )
        
    if not candidates:
        lines.append("| - | - | - | - | - | - | - | - | - | - | ℹ️ 조건 충족 후보 없음 |")
        
    lines.append("")
    lines.append("## 🔍 후보군 후속 조치 계획")
    lines.append("- [ ] **EXCELLENT (8.0점 이상)**: 실시간 장중 호가 잔량 및 호가창 지지 강도를 추가 분석하여 최종 Watch/Probe 진입 타겟으로 등록.")
    lines.append("- [ ] **PASS (5.0점 이상)**: 수급 주체의 연속 매집 지속 여부를 모니터링하며 주가가 평단가 아래로 눌리는 시점을 추적.")
    lines.append("")
    lines.append("---")
    lines.append("*본 보드는 모의 테스트 분석 자료이며, 실거래 투자 권유가 아닙니다.*")
    
    output_md.parent.mkdir(parents=True, exist_ok=True)
    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"✅ Created candidate board at: {output_md}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
