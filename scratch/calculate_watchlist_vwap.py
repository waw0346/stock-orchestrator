import csv
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "picks" / "cache" / "foreign_flow_history.csv"
JSON_PATH = ROOT / "picks" / "cache" / "flow_comparison_history.json"
MARKET_SNAPSHOT_PATH = ROOT / "picks" / "cache" / "market_data_snapshot.json"

WATCHLIST = {
    "005930": "삼성전자",
    "402340": "SK스퀘어",
    "000660": "SK하이닉스",
    "042700": "한미반도체",
    "006400": "삼성SDI",
    "001440": "대한전선",
    "347700": "스피어",
    "454910": "두산로보틱스",
    "046890": "서울반도체",
    "066570": "LG전자",
    "207940": "삼성바이오로직스",
    "353200": "대덕전자",
    "009150": "삼성전기",
    "077360": "덕산하이메탈"
}

def parse_int(val):
    if val is None or val == "":
        return 0
    try:
        return int(float(str(val).replace(",", "")))
    except ValueError:
        return 0

def clean_int(value) -> int:
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

def standardize_flow(net_buy, close_price, volume):
    if close_price <= 0:
        return 0
    abs_net_buy = abs(net_buy)
    if abs_net_buy == 0:
        return 0
    if abs_net_buy > volume:
        shares = abs_net_buy / close_price
        if shares <= volume:
            return int(net_buy / close_price)
        shares_k = (abs_net_buy * 1000) / close_price
        if shares_k <= volume:
            return int((net_buy * 1000) / close_price)
        return int(net_buy / close_price)
    return int(net_buy)

def calculate_vwap_for_ticker(ticker, data_points):
    # Sort data by date ascending
    sorted_points = sorted(data_points, key=lambda x: x["date"])
    
    # Calculate streak from the latest date backwards
    streak_len = 0
    streak_points = []
    
    for r in reversed(sorted_points):
        if r["net_buy"] <= 0:
            break
        streak_len += 1
        streak_points.append(r)
        
    streak_points.reverse()
    
    if streak_len == 0:
        # Fallback to last N days of positive net buy if no streak exists, or just use all positive days
        streak_points = [r for r in sorted_points if r["net_buy"] > 0]
        streak_len = len(streak_points)
        
    if not streak_points:
        return None
        
    total_net_buy = sum(r["net_buy"] for r in streak_points)
    if total_net_buy <= 0:
        return None
        
    # Model 1: VWAP of Net Buy
    p_vwap = sum(r["close"] * r["net_buy"] for r in streak_points) / total_net_buy
    
    # Model 2: Intensity-Weighted Price
    intensity_sum = 0.0
    weighted_intensity_price = 0.0
    for r in streak_points:
        vol = r["volume"]
        net_buy = r["net_buy"]
        if vol > 0:
            weight = float(net_buy) / float(vol)
            intensity_sum += weight
            weighted_intensity_price += r["close"] * weight
    p_intensity = (weighted_intensity_price / intensity_sum) if intensity_sum > 0 else p_vwap
    
    # Model 3: Value-Weighted Price
    val_denom = sum(r["volume"] * r["net_buy"] for r in streak_points)
    p_value_vwap = sum(r["close"] * r["volume"] * r["net_buy"] for r in streak_points) / val_denom if val_denom > 0 else p_vwap
    
    return {
        "streak": streak_len,
        "total_net_buy": total_net_buy,
        "latest_close": sorted_points[-1]["close"],
        "latest_date": sorted_points[-1]["date"],
        "p_vwap": p_vwap,
        "p_intensity": p_intensity,
        "p_value_vwap": p_value_vwap
    }

def main():
    ticker_data = defaultdict(list)
    
    # 1. Load CSV data
    if CSV_PATH.exists():
        with CSV_PATH.open("r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = str(row.get("ticker", "")).strip().zfill(6)
                if ticker in WATCHLIST:
                    date = row.get("date")
                    close = parse_int(row.get("close"))
                    volume = parse_int(row.get("volume"))
                    net_buy = clean_int(row.get("foreign_net_buy")) # Focus on foreign flow
                    net_buy_shares = standardize_flow(net_buy, close, volume)
                    
                    ticker_data[ticker].append({
                        "date": date,
                        "close": close,
                        "volume": volume,
                        "net_buy": net_buy_shares,
                        "source": "csv"
                    })
                    
    # 2. Load JSON data and merge
    if JSON_PATH.exists():
        try:
            json_data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
            for date_str, date_content in json_data.items():
                # Format date to match YYYY-MM-DD
                formatted_date = date_str
                intraday = date_content.get("intraday", {})
                
                # Check foreign_buy list
                for item in intraday.get("foreign_buy", []):
                    ticker = str(item.get("ticker", "")).strip().zfill(6)
                    if ticker in WATCHLIST:
                        # Avoid duplicates
                        if not any(x["date"] == formatted_date and x["ticker"] == ticker for x in ticker_data.get(ticker, [])):
                            close = parse_int(item.get("close"))
                            volume = parse_int(item.get("volume"))
                            net_buy = parse_int(item.get("net_buy"))
                            net_buy_shares = standardize_flow(net_buy, close, volume)
                            
                            ticker_data[ticker].append({
                                "date": formatted_date,
                                "close": close,
                                "volume": volume,
                                "net_buy": net_buy_shares,
                                "source": "json"
                            })
                            
                # Check institution_buy list
                for item in intraday.get("institution_buy", []):
                    ticker = str(item.get("ticker", "")).strip().zfill(6)
                    if ticker in WATCHLIST:
                        # If foreign buy is not present, we can use institution buy as fallback
                        if not any(x["date"] == formatted_date and x["ticker"] == ticker for x in ticker_data.get(ticker, [])):
                            close = parse_int(item.get("close"))
                            volume = parse_int(item.get("volume"))
                            net_buy = parse_int(item.get("net_buy"))
                            net_buy_shares = standardize_flow(net_buy, close, volume)
                            
                            ticker_data[ticker].append({
                                "date": formatted_date,
                                "close": close,
                                "volume": volume,
                                "net_buy": net_buy_shares,
                                "source": "json_inst"
                            })
        except Exception as exc:
            print(f"Error parsing JSON: {exc}")
            
    # Load current prices from market snapshot as a fallback
    market_prices = {}
    if MARKET_SNAPSHOT_PATH.exists():
        try:
            market_data = json.loads(MARKET_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            for item in market_data.get("items", []):
                ticker = str(item.get("ticker", "")).strip().zfill(6)
                market_prices[ticker] = parse_int(item.get("price"))
        except Exception:
            pass

    print("\n=== 관찰종목 세력평균단가 (VWAP) 계산 결과 ===")
    print(f"{'종목명 (코드)':<15} | {'최근 종가':<10} | {'기준일':<10} | {'순매수일수':<6} | {'Model 1 (VWAP)':<12} | {'Model 2 (Int)':<12} | {'Model 3 (Val)':<12}")
    print("-" * 90)
    
    results = {}
    for ticker, name in WATCHLIST.items():
        points = ticker_data.get(ticker, [])
        if not points:
            # Fallback when no daily flow exists: use current price
            cur_price = market_prices.get(ticker, 0)
            if cur_price > 0:
                print(f"{name:<10}({ticker}) | {cur_price:>8,}원 | N/A        | N/A    | {cur_price:>10,}원* | {cur_price:>10,}원* | {cur_price:>10,}원*  (수급 데이터 없음)")
            continue
            
        vwap_res = calculate_vwap_for_ticker(ticker, points)
        if vwap_res is None:
            cur_price = market_prices.get(ticker, 0)
            if cur_price > 0:
                print(f"{name:<10}({ticker}) | {cur_price:>8,}원 | N/A        | N/A    | {cur_price:>10,}원* | {cur_price:>10,}원* | {cur_price:>10,}원*  (순매수 내역 없음)")
            continue
            
        results[ticker] = vwap_res
        print(f"{name:<10}({ticker}) | {vwap_res['latest_close']:>8,}원 | {vwap_res['latest_date']:<10} | {vwap_res['streak']:>4}일 | {int(vwap_res['p_vwap']):>10,}원 | {int(vwap_res['p_intensity']):>10,}원 | {int(vwap_res['p_value_vwap']):>10,}원")

    # Write output JSON to scratch directory for verification
    output_json_path = ROOT / "scratch" / "watchlist_vwap_results.json"
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with output_json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved raw calculations to: {output_json_path}")

if __name__ == "__main__":
    main()
