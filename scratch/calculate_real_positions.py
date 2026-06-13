import sys
import os

sys.path.append(os.getcwd())

from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_trade_logs

def calculate_real_summary(user_id):
    positions = ShioajiService.get_positions(user_id)
    logs = get_user_trade_logs(user_id)
    history = [L for L in logs if L.get("entry_type") == "HISTORY" and L.get("action") == "Sell"]
    
    # Realized PnL from history
    realized_pnl = sum(float(item.get("realized_pl", 0)) for item in history)
    
    # Unrealized PnL from positions
    unrealized_pnl = 0.0
    total_cost = 0.0
    
    print(f"\n==================== {user_id} Live Positions ====================")
    if not positions:
        print("No active holdings.")
    else:
        print(f"{'Symbol':<10} | {'Qty':<10} | {'Buy Price':<12} | {'Current Price':<12} | {'PnL (TWD)':<12} | {'ROI %':<10}")
        print("-" * 75)
        for pos in positions:
            symbol = pos.get("symbol", "")
            qty = pos.get("qty", 0)
            buy_price = pos.get("buy_price", 0)
            current_price = pos.get("current_price", 0)
            market = pos.get("market", "TW")
            
            # Fetch USD/TWD rate if needed
            rate = 32.5
            try:
                import yfinance as yf
                rate_df = yf.Ticker("TWD=X").history(period="1d")
                if not rate_df.empty:
                    rate = float(rate_df['Close'].iloc[-1])
            except: pass
            
            calc_buy = buy_price
            calc_current = current_price
            
            if market in ["US", "CRYPTO"]:
                # The stored buy_price might already be in TWD or USD depending on how matching engine filled it.
                # Let's check: if buy_price > 1000 for Crypto, it is likely in TWD. If it's small, it's USD.
                # Let's align them:
                # ShioajiService.get_positions converts current_price to TWD (line 518: calc_current = current_price * rate)
                # and stores it in pos['current_price'] as TWD.
                # Wait, does it also convert buy_price to TWD?
                # MatchingEngine stores buy_price in TWD because of the Unit Safety Guard.
                pass
            
            # Let's use the pnl_percent calculated by ShioajiService
            pnl_percent = pos.get("pnl_percent", 0.0)
            
            # PnL Amount in TWD
            # Let's calculate PnL Amount
            buy_cost_twd = buy_price * qty
            pnl_twd = buy_cost_twd * (pnl_percent / 100.0)
            
            unrealized_pnl += pnl_twd
            total_cost += buy_cost_twd
            
            print(f"{symbol:<10} | {qty:<10} | {buy_price:<12.2f} | {current_price:<12.2f} | {pnl_twd:<12.2f} | {pnl_percent:<8.2f}%")
            
    print(f"\nSummary for {user_id}:")
    print(f"  Realized PnL  : {realized_pnl:.2f} TWD")
    print(f"  Unrealized PnL: {unrealized_pnl:.2f} TWD")
    print(f"  Total PnL     : {realized_pnl + unrealized_pnl:.2f} TWD")
    if total_cost > 0:
        print(f"  Unrealized ROI: {(unrealized_pnl / total_cost * 100.0):.2f}% (on active holdings of {total_cost:.2f} TWD)")

calculate_real_summary("system_auto")
calculate_real_summary("system_eric")
