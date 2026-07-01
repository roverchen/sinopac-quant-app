import os
import sys
import json

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, save_user_trade_logs

def fix_enstwd():
    uid = "system_auto"
    print(f"Loading logs for {uid}...")
    logs = get_user_trade_logs(uid)
    modified = False
    
    for item in logs:
        entry_type = item.get("entry_type")
        symbol = item.get("symbol")
        
        if entry_type == "POSITION" and symbol == "enstwd":
            old_buy = item.get("buy_price")
            # Calculate correct average buy price including fees from sub_orders
            # Sub-orders:
            # 1. qty = 1.914, buy_price = 168.54, fee = 10.0 => 332.59
            # 2. qty = 1.918, buy_price = 168.18, fee = 10.0 => 332.58
            # 3. qty = 1.9314, buy_price = 167.02, fee = 10.0 => 332.68
            # Total qty = 5.7634, Total cost with fees = 997.85 TWD
            # Correct average price = 997.85 / 5.7634 = 173.14 TWD
            new_buy = 173.14
            item["buy_price"] = new_buy
            if "message" in item:
                item["message"] = "Fixed enstwd position buy_price corrupted by hotfix ROI heuristic"
            print(f"Fixed enstwd position buy_price: {old_buy} -> {new_buy} TWD")
            modified = True
            
    if modified:
        save_user_trade_logs(uid, logs)
        print("✅ Corrected trade logs saved to Firestore.")
    else:
        print("enstwd position not found or already corrected.")

if __name__ == "__main__":
    fix_enstwd()
