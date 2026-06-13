import sys
import os
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs

def calc_pnl(user_id):
    logs = get_user_trade_logs(user_id)
    total_pnl = 0
    trades = []
    for item in logs:
        if item.get("entry_type") == "HISTORY" and item.get("action", "").upper() == "SELL":
            pnl = float(item.get("realized_pl", 0))
            symbol = item.get("symbol", "")
            pnl_percent = float(item.get("pnl_percent", 0))
            sell_time = item.get("timestamp") or item.get("sell_time") or ""
            trades.append((sell_time, symbol, pnl, pnl_percent))
            total_pnl += pnl

    trades.sort(key=lambda x: str(x[0]), reverse=True)
    return total_pnl, trades

for user_id in ["system_auto", "system_eric"]:
    total_pnl, trades = calc_pnl(user_id)
    print(f"\n{'='*40}")
    print(f"Strategy: {user_id}")
    print(f"Total Realized PnL: {total_pnl:.2f} TWD")
    print(f"{'Time':<20} | {'Symbol':<15} | {'PnL (TWD)':<12} | {'ROI %':<10}")
    print("-" * 65)
    for t in trades[:15]:  # Show last 15
        time_str = str(t[0])[:16].replace('T', ' ')
        print(f"{time_str:<20} | {str(t[1]):<15} | {t[2]:<12.2f} | {t[3]:<8.2f}%")
