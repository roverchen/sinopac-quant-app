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
            if item.get("entry_type") == "HISTORY" and item.get("action") == "Sell":
                symbol = item.get("symbol", "")
                market = item.get("market", "")
                pnl_pct = item.get("pnl_percent", 0)
                
                # Identify broken trades (ROI near -97% for US/Crypto)
                if market in ["US", "CRYPTO"] and pnl_pct < -90:
                    old_pnl = item.get("realized_pl", 0)
                    old_pct = pnl_pct
                    
                    price = item.get("price", 0)
                    buy_price = item.get("buy_price", 0)
                    qty = item.get("qty", 0)
                    
                    # Correction: Assume price was USD, convert to TWD
                    correct_sell_price_twd = price * rate
                    correct_realized_pl = (correct_sell_price_twd - buy_price) * qty
                    
                    # Account for fees (rough estimate based on MatchingEngine)
                    fee = (correct_sell_price_twd * qty) * 0.001
                    correct_realized_pl -= fee
                    
                    correct_pct = round((correct_realized_pl / (buy_price * qty)) * 100, 2) if (buy_price * qty) > 0 else 0
                    
                    item["realized_pl"] = round(correct_realized_pl, 2)
                    item["pnl_percent"] = correct_pct
                    item["message"] = f"Hotfix: Corrected currency mismatch (Original ROI: {old_pct}%)"
                    
                    print(f"  [FIXED] {symbol}: {old_pct}% -> {correct_pct}% (PnL: {old_pnl} -> {item['realized_pl']})")
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
