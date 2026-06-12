import json
import os
import sys

def configure_stdio() -> None:
    """Prefer UTF-8 console output when supported."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def main():
    configure_stdio()
    state_path = "picks/paper_trading_state.json"
    price_path = "picks/paper_price_snapshot.json"
    
    if not os.path.exists(state_path) or not os.path.exists(price_path):
        print("Required files not found.")
        return
        
    with open(state_path, "r", encoding="utf-8-sig") as f:
        state = json.load(f)
    with open(price_path, "r", encoding="utf-8-sig") as f:
        prices = json.load(f)
        
    cash = state.get("cash", 0.0)
    realized_pnl = state.get("realized_pnl", 0.0)
    positions = state.get("positions", [])
    current_prices = prices.get("prices", {})
    
    initial_assets = 100000000.0  # 1억 원
    
    print("=========================================================================")
    print("                   📊 모의 투자 포트폴리오 실적 현황")
    print("=========================================================================")
    print(f"기준 시간: {prices.get('date', 'N/A')}")
    print(f"예수금(현금): {cash:,.0f} 원")
    print(f"누적 실현 손익: {realized_pnl:+,.0f} 원")
    print("-------------------------------------------------------------------------")
    print(f"{'종목명 (코드)':<15} | {'수량':<5} | {'평균단가':<10} | {'현재가':<10} | {'평가금액':<11} | {'평가손익 (수익률)':<20}")
    print("-------------------------------------------------------------------------")
    
    total_cost = 0.0
    total_value = 0.0
    
    for pos in positions:
        ticker = pos.get("ticker")
        name = pos.get("name")
        qty = pos.get("quantity")
        avg_price = pos.get("avg_price")
        
        cur_price = current_prices.get(ticker, avg_price)
        cost_basis = avg_price * qty
        val = cur_price * qty
        unrealized = val - cost_basis
        unrealized_pct = (unrealized / cost_basis) * 100.0 if cost_basis > 0 else 0.0
        
        total_cost += cost_basis
        total_value += val
        
        ticker_display = f"{name} ({ticker})"
        print(f"{ticker_display:<15} | {qty:<5} | {avg_price:,.0f} | {cur_price:,.0f} | {val:,.0f} | {unrealized:+,.0f} ({unrealized_pct:+.2f}%)")
        
    total_unrealized = total_value - total_cost
    total_unrealized_pct = (total_unrealized / total_cost) * 100.0 if total_cost > 0 else 0.0
    total_portfolio_val = cash + total_value
    net_pnl = realized_pnl + total_unrealized
    roi = (net_pnl / initial_assets) * 100.0
    
    print("-------------------------------------------------------------------------")
    print(f"주식 평가 총액: {total_value:,.0f} 원 (투자 원금: {total_cost:,.0f} 원)")
    print(f"총 평가 손익: {total_unrealized:+,.0f} 원 ({total_unrealized_pct:+.2f}%)")
    print(f"포트폴리오 총자산: {total_portfolio_val:,.0f} 원")
    print(f"총 누적 손익 (실현+평가): {net_pnl:+,.0f} 원")
    print(f"총 투자 수익률 (ROI): {roi:+.2f}% (최초 원금 1억 원 기준)")
    print("=========================================================================")

if __name__ == "__main__":
    main()
