import os
import sys
import json
from datetime import datetime

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, save_user_trade_logs

def fix_logs():
    uids = ["system_auto", "system_eric", "rover.k.chen@gmail.com"]
    rate = 31.72
    
    for uid in uids:
        logs = get_user_trade_logs(uid)
        modified = False
        
        for item in logs:
            market = item.get("market", "")
            symbol = item.get("symbol", "")
            entry_type = item.get("entry_type", "")
            
            # Target double-converted TWD crypto pairs (e.g. usdttwd, usdctwd)
            if market == "CRYPTO" and ("TWD" in symbol.upper() or symbol.upper().endswith("TWD")):
                buy_price = item.get("buy_price", 0)
                # If buy_price is abnormally high (e.g. > 200 for a stablecoin or token that should be ~30)
                if buy_price > 200:
                    old_price = buy_price
                    new_price = round(buy_price / rate, 2)
                    item["buy_price"] = new_price
                    print(f"[{uid}] Fixed {entry_type} {symbol}: buy_price {old_price} -> {new_price} TWD")
                    
                    # Also fix sub_orders if present
                    if "sub_orders" in item:
                        for sub in item["sub_orders"]:
                            sub_price = sub.get("buy_price", 0)
                            if sub_price > 200:
                                sub["buy_price"] = round(sub_price / rate, 2)
                                print(f"  Fixed sub_order buy_price {sub_price} -> {sub['buy_price']} TWD")
                    
                    modified = True
                    
        if modified:
            save_user_trade_logs(uid, logs)
            print(f"✅ Saved updated trade logs for {uid}")

if __name__ == "__main__":
    fix_logs()
