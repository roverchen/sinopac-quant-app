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
            
            # --- FIX 1: Active Positions ---
            if item.get("entry_type") == "POSITION" and market in ["US", "CRYPTO"]:
                buy_price = item.get("buy_price", 0)
                # If buy_price is suspiciously low (looks like USD), convert it to TWD
                # MSFT at 371 is clearly USD. MSFT at 11000 is TWD.
                # Threshold: If buy_price < 2000 and market is US/Crypto, it's likely USD.
                # (LTC at 55 is USD, LTC at 1700 is TWD).
                if 0 < buy_price < 1000: 
                    old_price = buy_price
                    item["buy_price"] = round(buy_price * rate, 2)
                    item["message"] = f"Recovery: Normalized position cost from USD to TWD (Rate: {rate:.2f})"
                    print(f"  [POSITION FIXED] {symbol}: {old_price} USD -> {item['buy_price']} TWD")
                    modified = True
                    total_fixed += 1

            # --- FIX 2: Historical Sells ---
            if item.get("entry_type") == "HISTORY" and item.get("action") == "Sell":
                pnl_pct = item.get("pnl_percent", 0)
                
                # Identify broken trades (ROI near -97% for US/Crypto)
                # [v2.7.2] Robust detection: ROI < -90% usually means currency mismatch
                if market in ["US", "CRYPTO"] and (pnl_pct < -90 or pnl_pct > 3000):
                    old_pnl = item.get("realized_pl", 0)
                    old_pct = pnl_pct
                    
                    price = item.get("price") or item.get("sell_price") or 0
                    buy_price = item.get("buy_price", 0)
                    qty = item.get("qty", 0)

                    # Determine if buy_price was already normalized
                    # If buy_price was 371, it needs normalization before PnL calculation
                    calc_buy = buy_price
                    if 0 < buy_price < 1000:
                        calc_buy = buy_price * rate
                    
                    # Correction: Price was USD, Cost is now calc_buy
                    correct_sell_price_twd = price * rate
                    correct_realized_pl = (correct_sell_price_twd - calc_buy) * qty
                    
                    # Fee estimate
                    fee = (correct_sell_price_twd * qty) * 0.001
                    correct_realized_pl -= fee
                    
                    cost_basis = (calc_buy * qty)
                    correct_pct = round((correct_realized_pl / cost_basis) * 100, 2) if cost_basis > 0 else 0
                    
                    item["realized_pl"] = round(correct_realized_pl, 2)
                    item["pnl_percent"] = correct_pct
                    item["status"] = "CLOSED" 
                    item["message"] = f"Recovery: Fixed currency mismatch. Real ROI: {correct_pct}% (was {old_pct}%)"
                    
                    print(f"  [HISTORY FIXED] {symbol}: {old_pct}% -> {correct_pct}% (PnL: {old_pnl} -> {item['realized_pl']})")
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
