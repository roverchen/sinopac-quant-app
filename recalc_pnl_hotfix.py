import os
import sys
import json
from datetime import datetime

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, save_user_trade_logs

def run_hotfix():
    user_id = "system_auto"
    print(f"--- [Hotfix] Recalculating PnL for {user_id} ---")
    
    logs = get_user_trade_logs(user_id)
    if not logs:
        print("No logs found.")
        return

    modified_count = 0
    exchange_rate = 32.5 # Approximate rate for recovery
    
    for log in logs:
        # We only care about HISTORY entries that are Sell actions and have suspiciously high negative ROI
        if log.get("entry_type") == "HISTORY" and log.get("action") == "Sell":
            pnl_pct = log.get("pnl_percent", 0)
            market = log.get("market")
            
            # Identify the bug: price is ~32x smaller than buy_price for US/Crypto
            if market in ["US", "CRYPTO"] and pnl_pct < -90:
                old_price = log.get("price", 0)
                old_pnl = log.get("realized_pl", 0)
                buy_price = log.get("buy_price", 0)
                qty = log.get("qty", 0)
                
                # Correction: Multiply price by exchange rate
                new_price = old_price * exchange_rate
                new_total_value = new_price * qty
                
                # Re-calculate costs (0.1% for US/Crypto)
                fee = new_total_value * 0.001
                tax = 0
                
                # New PnL = (New Total Value - Fee) - (Buy Price * Qty)
                new_pnl = (new_total_value - fee) - (buy_price * qty)
                new_pnl_pct = round((new_pnl / (buy_price * qty)) * 100, 2) if buy_price > 0 else 0
                
                print(f"Fixing {log.get('symbol')}: {old_price} -> {new_price:.2f} | PnL: {old_pnl} -> {new_pnl:.2f} ({new_pnl_pct}%)")
                
                log["price"] = round(new_price, 2)
                log["realized_pl"] = round(new_pnl, 2)
                log["pnl_percent"] = new_pnl_pct
                log["fee"] = round(fee, 2)
                modified_count += 1

    if modified_count > 0:
        save_user_trade_logs(user_id, logs)
        print(f"Successfully updated {modified_count} trade records.")
    else:
        print("No suspicious trades found to fix.")

if __name__ == "__main__":
    run_hotfix()
