import sys
import os
import json
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, get_user_mock_positions

def get_all_trades(user_id):
    logs = get_user_trade_logs(user_id)
    all_trades = []
    
    # Extract from positions (current holdings)
    for entry in logs:
        if entry.get("entry_type") == "POSITION":
            # Check sub_orders for multiple buys
            sub_orders = entry.get("sub_orders", [])
            if sub_orders:
                for so in sub_orders:
                    all_trades.append({
                        "time": so.get("fill_time") or so.get("buy_order_time") or entry.get("timestamp"),
                        "symbol": entry.get("symbol"),
                        "name": entry.get("name"),
                        "action": "BUY",
                        "qty": so.get("qty"),
                        "price": so.get("buy_price"),
                        "market": entry.get("market"),
                        "status": "Holding"
                    })
            else:
                all_trades.append({
                    "time": entry.get("timestamp") or entry.get("buy_order_time"),
                    "symbol": entry.get("symbol"),
                    "name": entry.get("name"),
                    "action": "BUY",
                    "qty": entry.get("qty"),
                    "price": entry.get("buy_price"),
                    "market": entry.get("market"),
                    "status": "Holding"
                })
        elif entry.get("entry_type") == "HISTORY":
            all_trades.append({
                "time": entry.get("timestamp") or entry.get("sell_time") or entry.get("buy_time"),
                "symbol": entry.get("symbol"),
                "name": entry.get("name"),
                "action": entry.get("action", "SELL"),
                "qty": entry.get("qty"),
                "price": entry.get("price") or entry.get("sell_price") or entry.get("buy_price"),
                "market": entry.get("market"),
                "status": "Closed"
            })
            
    # Sort by time descending
    all_trades.sort(key=lambda x: str(x.get("time")), reverse=True)
    return all_trades

def render_table(user_id, label):
    trades = get_all_trades(user_id)
    if not trades:
        return f"### {label} ({user_id})\n無交易紀錄。"
    
    lines = [f"### {label} ({user_id}) - 最近 15 筆交易"]
    lines.append("| 時間 | 標的 | 動作 | 數量 | 價格 | 市場 | 狀態 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for t in trades[:15]:
        time_str = str(t['time'])[:16].replace('T', ' ')
        symbol = t['symbol']
        name = t['name'] or ""
        action = t['action']
        qty = t['qty']
        price = f"{t['price']:.2f}" if isinstance(t['price'], (int, float)) else t['price']
        market = t['market']
        status = t['status']
        lines.append(f"| {time_str} | {symbol} {name} | {action} | {qty} | {price} | {market} | {status} |")
    
    return "\n".join(lines)

print(render_table("system_auto", "Rover 核心策略"))
print("\n" + "="*80 + "\n")
print(render_table("system_eric", "Eric 波段策略"))
