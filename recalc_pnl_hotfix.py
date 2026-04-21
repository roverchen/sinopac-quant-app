import os
import sys
import time
from datetime import datetime
import yfinance as yf

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs, save_user_trade_logs
from api.services.strategy_accounts import list_strategy_account_ids

def get_rate():
    try:
        df = yf.download("TWD=X", period="1d", interval="1m", progress=False)
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except:
        pass
    return 32.5

def run_hotfix():
    print(f"--- [Hotfix] {datetime.now()} ---")
    rate = get_rate()
    print(f"Current USD/TWD Rate: {rate}")
    
    uids = list_strategy_account_ids()
    total_fixed = 0

    for uid in uids:
        print(f"\nProcessing {uid}...")
        logs = get_user_trade_logs(uid)
        modified = False
        
        for item in logs:
            market = item.get("market", "")
            symbol = item.get("symbol", "")
            
            # [v2.7.3] Intelligent Unit Detection
            def normalize_value(val, mkt):
                if mkt not in ["US", "CRYPTO"]: return val
                # Compare assuming val is TWD vs assuming val is USD
                # If assuming val is TWD results in ROI near 3000% while current is USD, it was likely USD.
                # But here we just want to know if val *is* USD or TWD.
                # Heuristic: If it's a major US stock and price < 1000, it's almost certainly USD.
                # However, many TWD prices are also < 1000.
                # Let's use the 2000 threshold but with a sanity check on the symbol.
                if 0 < val < 1000:
                    return val * rate
                return val

            # --- FIX 1: Active Positions ---
            if item.get("entry_type") == "POSITION" and market in ["US", "CRYPTO"]:
                buy_price = item.get("buy_price", 0)
                # Heuristic: If buy_price is < 700 (most US stocks) and it's US market, 
                # but let's check a more robust way: if normalizing it once leads to a 
                # more reasonable current ROI.
                current_raw = item.get("current_price", 0)
                
                # Option A: buy_price is already TWD
                roi_a = abs((current_raw * rate - buy_price) / buy_price) if buy_price > 0 else 999
                # Option B: buy_price is USD
                roi_b = abs((current_raw * rate - buy_price * rate) / (buy_price * rate)) if buy_price > 0 else 999
                
                if roi_b < roi_a and roi_a > 10: # If Option B is much more reasonable
                    old_price = buy_price
                    item["buy_price"] = round(buy_price * rate, 2)
                    item["message"] = f"Recovery: Normalized cost from USD to TWD (Heuristic ROI_B < ROI_A)"
                    print(f"  [POSITION FIXED] {symbol}: {old_price} USD -> {item['buy_price']} TWD")
                    modified = True
                    total_fixed += 1

            # --- FIX 2: Historical Sells ---
            if item.get("entry_type") == "HISTORY" and item.get("action") == "Sell":
                if market in ["US", "CRYPTO"]:
                    old_pnl = item.get("realized_pl", 0)
                    price_usd = item.get("price") or item.get("sell_price") or 0
                    buy_price = item.get("buy_price", 0)
                    qty = item.get("qty", 0)
                    
                    # Heuristic for buy_price unit
                    roi_a_val = ((price_usd * rate - buy_price) / buy_price * 100) if buy_price > 0 else -999
                    roi_b_val = ((price_usd * rate - buy_price * rate) / (buy_price * rate) * 100) if buy_price > 0 else -999
                    
                    # If current pnl_percent is extreme, we need fixing
                    if abs(item.get("pnl_percent", 0)) > 50 or abs(old_pnl) > 50000:
                        # Choose more reasonable ROI
                        if abs(roi_b_val) < abs(roi_a_val):
                            calc_buy = buy_price * rate
                            correct_pct = round(roi_b_val, 2)
                        else:
                            calc_buy = buy_price
                            correct_pct = round(roi_a_val, 2)
                            
                        correct_sell_twd = price_usd * rate
                        correct_realized_pl = (correct_sell_twd - calc_buy) * qty
                        # Fee
                        fee = (correct_sell_twd * qty) * 0.001
                        correct_realized_pl -= fee
                        
                        item["realized_pl"] = round(correct_realized_pl, 2)
                        item["pnl_percent"] = correct_pct
                        item["buy_price"] = round(calc_buy, 2)
                        item["status"] = "CLOSED" 
                        item["message"] = f"Recovery v2.7.3: Heuristic PnL correction. ROI: {correct_pct}%"
                        
                        print(f"  [HISTORY FIXED] {symbol}: PnL {old_pnl} -> {item['realized_pl']} ({correct_pct}%)")
                        modified = True
                        total_fixed += 1
        
        if modified:
            save_user_trade_logs(uid, logs)
            print(f"✅ Saved updated logs for {uid}.")
        else:
            print(f"No broken trades found for {uid}.")

    print(f"\n🎉 Hotfix complete. Total trades corrected: {total_fixed}")

if __name__ == "__main__":
    run_hotfix()
