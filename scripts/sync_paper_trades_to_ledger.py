import os
import json
from datetime import datetime, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
RULES_PATH = os.path.join(PROJECT_ROOT, 'picks', 'paper_trading_rules.json')
LEDGER_PATH = os.path.join(PROJECT_ROOT, 'obsidian', 'stock_log', '09_decision_journal', 'portfolio.ledger')

def convert_to_ledger():
    print(f"Reading paper trading rules from: {RULES_PATH}")
    if not os.path.exists(RULES_PATH):
        print("Error: paper_trading_rules.json not found.")
        return

    with open(RULES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Initial cash setup
    initial_cash = 100000000  # 100,000,000 KRW
    cash_currency = data.get("cash_currency", "KRW")

    ledger_transactions = [
        "; ==================================================",
        "; 📊 Stock Orchestrator Portfolio Ledger",
        "; Generated automatically from paper trading rules",
        "; ==================================================\n",
        "2026-05-01 * Opening Balance",
        f"    Assets:Brokerage:Cash             {initial_cash} {cash_currency}",
        "    Equity:Opening Balances\n"
    ]

    current_cash = initial_cash

    for pos in data.get("positions", []):
        ticker = pos.get("ticker")
        name = pos.get("name")
        status = pos.get("status")

        if status == "closed":
            close_date_str = pos.get("close_date", "2026-05-01")
            close_date = datetime.strptime(close_date_str, "%Y-%m-%d")
            # Assume buy date is 7 days prior for timeline representation
            buy_date = close_date - timedelta(days=7)
            buy_date_str = buy_date.strftime("%Y-%m-%d")

            close_price = int(pos.get("close_price", 0))
            pnl_pct = float(pos.get("realized_pnl_pct", 0))
            
            # Reconstruct buy price based on close price and PnL %
            # pnl_pct = ((close_price - buy_price) / buy_price) * 100
            # buy_price * (1 + pnl_pct/100) = close_price
            # buy_price = close_price / (1 + pnl_pct/100)
            buy_price = int(close_price / (1 + pnl_pct / 100.0))
            
            # Assume a standardized trade size: 10 shares
            shares = 10
            buy_total = buy_price * shares
            sell_total = close_price * shares
            realized_pnl = sell_total - buy_total

            # Buy transaction
            ledger_transactions.append(f"{buy_date_str} * {name} ({ticker}) Buy")
            ledger_transactions.append(f"    Assets:Brokerage:Stocks             {shares} {ticker} @ {buy_price} {cash_currency}")
            ledger_transactions.append(f"    Assets:Brokerage:Cash             -{buy_total} {cash_currency}\n")
            
            # Sell transaction
            ledger_transactions.append(f"{close_date_str} * {name} ({ticker}) Sell (PnL: {pnl_pct}%)")
            ledger_transactions.append(f"    Assets:Brokerage:Stocks            -{shares} {ticker} @ {close_price} {cash_currency}")
            ledger_transactions.append(f"    Assets:Brokerage:Cash              {sell_total} {cash_currency}")
            ledger_transactions.append(f"    Income:Realized PnL               -{realized_pnl} {cash_currency}\n")
            
            current_cash = current_cash - buy_total + sell_total

        elif status == "active":
            # Assume bought on 2026-06-01
            buy_date_str = "2026-06-01"
            entry_low = int(pos.get("entry_low", 0))
            entry_high = int(pos.get("entry_high", 0))
            buy_price = int((entry_low + entry_high) / 2) # Average entry
            
            shares = 15  # Assume 15 shares for active holding
            buy_total = buy_price * shares

            # Buy transaction
            ledger_transactions.append(f"{buy_date_str} * {name} ({ticker}) Buy [ACTIVE]")
            ledger_transactions.append(f"    Assets:Brokerage:Stocks             {shares} {ticker} @ {buy_price} {cash_currency}")
            ledger_transactions.append(f"    Assets:Brokerage:Cash             -{buy_total} {cash_currency}\n")

            current_cash -= buy_total

    # Write the ledger file
    os.makedirs(os.path.dirname(LEDGER_PATH), exist_ok=True)
    with open(LEDGER_PATH, 'w', encoding='utf-8') as lf:
        lf.write('\n'.join(ledger_transactions))
        
    print(f"Ledger file successfully initialized and synced at: {LEDGER_PATH}")

if __name__ == '__main__':
    convert_to_ledger()
