import os
import sys
import json

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, save_user_trade_logs

def run_fix():
    uid = "system_auto"
    print(f"Loading logs for {uid}...")
    logs = get_user_trade_logs(uid)
    modified = False
    
    for item in logs:
        entry_type = item.get("entry_type")
        symbol = item.get("symbol")
        trade_id = item.get("trade_id")
        
        # 1. Fix open USDC position
        if entry_type == "POSITION" and symbol == "usdctwd":
            old_buy = item.get("buy_price")
            # Correct buy price including fee: (31.604468884361268 * 10.2068 + 10.0) / 10.2068 = 32.5843
            new_buy = 32.58
            item["buy_price"] = new_buy
            print(f"Fixed open USDC position buy_price: {old_buy} -> {new_buy} TWD")
            modified = True
            
        # 2. Fix historical USDC sell (SIM-5194)
        elif entry_type == "HISTORY" and trade_id == "SIM-5194":
            old_buy = item.get("buy_price")
            old_pl = item.get("realized_pl")
            old_pct = item.get("pnl_percent")
            
            # Correct values:
            # qty = 112.4094, price = 31.6 TWD, buy_price = 30.87 TWD, fee = 110.12 TWD
            # total_value = 31.6 * 112.4094 = 3552.14
            # buy_cost = 30.87 * 112.4094 = 3470.08
            # PL = 3552.14 - 3470.08 - 110.12 = -28.06
            # Pct = -28.06 / 3470.08 * 100 = -0.81%
            item["buy_price"] = 30.87
            item["realized_pl"] = -28.06
            item["pnl_percent"] = -0.81
            
            print(f"Fixed historical USDC sell (SIM-5194):")
            print(f"  buy_price: {old_buy} -> 30.87 TWD")
            print(f"  realized_pl: {old_pl} -> -28.06 TWD")
            print(f"  pnl_percent: {old_pct}% -> -0.81%")
            modified = True
            
        # 3. Fix historical USDT sell (SIM-6914)
        elif entry_type == "HISTORY" and trade_id == "SIM-6914":
            old_buy = item.get("buy_price")
            old_pl = item.get("realized_pl")
            old_pct = item.get("pnl_percent")
            
            # Correct values:
            # qty = 61.5874, price = 31.57 TWD, buy_price = 30.74 TWD, fee = 60.27 TWD
            # total_value = 31.57 * 61.5874 = 1944.31
            # buy_cost = 30.74 * 61.5874 = 1893.20
            # PL = 1944.31 - 1893.20 - 60.27 = -9.16
            # Pct = -9.16 / 1893.20 * 100 = -0.48%
            item["buy_price"] = 30.74
            item["realized_pl"] = -9.16
            item["pnl_percent"] = -0.48
            
            print(f"Fixed historical USDT sell (SIM-6914):")
            print(f"  buy_price: {old_buy} -> 30.74 TWD")
            print(f"  realized_pl: {old_pl} -> -9.16 TWD")
            print(f"  pnl_percent: {old_pct}% -> -0.48%")
            modified = True
            
    if modified:
        save_user_trade_logs(uid, logs)
        print("✅ Corrected trade logs saved to Firestore and local cache.")
    else:
        print("No broken trade records found.")

if __name__ == "__main__":
    run_fix()
