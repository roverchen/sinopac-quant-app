import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, get_user_mock_positions
from datetime import datetime

def format_trades(user_id):
    logs = get_user_trade_logs(user_id)
    if not logs:
        return f"No trades for {user_id}"
    
    # Sort by timestamp descending
    logs.sort(key=lambda x: x.get("timestamp", x.get("buy_time", "")), reverse=True)
    
    output = []
    # History
    history = [L for L in logs if L.get("entry_type") == "HISTORY" or L.get("status") == "FILLED"]
    if history:
        output.append(f"### {user_id} Trade History (Recent 10)")
        output.append("| Time | Symbol | Action | Price | Market | PnL% |")
        output.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for log in history[:10]:
            ts = log.get("timestamp", log.get("buy_time", "N/A"))
            symbol = log.get("symbol", "N/A")
            action = log.get("action", "Trade")
            price = log.get("price", log.get("buy_price", "N/A"))
            market = log.get("market", "N/A")
            pnl_pct = log.get("pnl_percent", "N/A")
            output.append(f"| {ts} | {symbol} | {action} | {price} | {market} | {pnl_pct} |")
    
    # Positions
    positions = get_user_mock_positions(user_id)
    if positions:
        output.append(f"\n### {user_id} Current Positions")
        output.append("| Symbol | Qty | Entry | Current | PnL% |")
        output.append("| :--- | :--- | :--- | :--- | :--- |")
        for pos in positions:
            symbol = pos.get("symbol", "N/A")
            qty = pos.get("qty", 0)
            entry = pos.get("entry_price", "N/A")
            current = pos.get("current_price", "N/A")
            pnl_pct = pos.get("pnl_percent", 0)
            output.append(f"| {symbol} | {qty} | {entry} | {current} | {pnl_pct}% |")
            
    return "\n".join(output)

print(format_trades("system_auto"))
print("\n" + "="*50 + "\n")
print(format_trades("system_eric"))
