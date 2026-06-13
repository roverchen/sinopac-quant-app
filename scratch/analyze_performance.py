import os
import sys
import json
from datetime import datetime

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs
from api.services.strategy_accounts import list_strategy_account_ids
from api.services.shioaji_service import ShioajiService

def analyze_user(user_id):
    logs = get_user_trade_logs(user_id)
    
    # Use ShioajiService.get_positions to get updated positions with current_price and PnL
    positions = ShioajiService.get_positions(user_id)
    history = [L for L in logs if L.get("entry_type") == "HISTORY"]
    pending = [L for L in logs if L.get("entry_type") == "PENDING"]
    
    print(f"\n==========================================")
    print(f"User: {user_id}")
    print(f"==========================================")
    print(f"Total Positions (Open): {len(positions)}")
    print(f"Total History (Closed/Cancelled): {len(history)}")
    print(f"Total Pending: {len(pending)}")
    
    # Get USD/TWD rate
    rate = 32.5
    try:
        import yfinance as yf
        rate_df = yf.Ticker("TWD=X").history(period="1d")
        if not rate_df.empty:
            rate = float(rate_df['Close'].iloc[-1])
    except: pass
    
    # 1. Open Positions Analysis
    total_unrealized_pl = 0.0
    total_position_cost = 0.0
    open_positions_detail = []
    
    for pos in positions:
        symbol = pos.get("symbol", "N/A")
        market = pos.get("market", "N/A")
        qty = pos.get("qty", 0.0)
        buy_price = pos.get("buy_price", 0.0) # In TWD
        current_price = pos.get("current_price", 0.0) # raw price (USD or TWD)
        pnl_percent = pos.get("pnl_percent", 0.0)
        
        # Calculate in TWD (get_positions now returns both in TWD)
        calc_buy = buy_price
        calc_current = current_price
        
        pnl = pos.get("unrealized_pl", 0.0)
        if not pnl:
            pnl = (calc_current - buy_price) * qty
        cost = buy_price * qty
        
        total_position_cost += cost
        total_unrealized_pl += pnl
        
        open_positions_detail.append({
            "symbol": symbol,
            "market": market,
            "qty": qty,
            "buy_price": buy_price,
            "current_price": current_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "cost": cost
        })
        
    # 2. Closed History Analysis
    total_realized_pl = 0.0
    total_closed_cost = 0.0
    win_count = 0
    loss_count = 0
    closed_detail = []
    
    for hist in history:
        # Ignore cancelled orders for PnL
        if hist.get("status") == "CANCELLED" or hist.get("action") == "Cancel":
            continue
            
        symbol = hist.get("symbol", "N/A")
        market = hist.get("market", "N/A")
        qty = hist.get("qty", 0.0)
        price = hist.get("price", 0.0) # sell price
        buy_price = hist.get("buy_price", 0.0)
        pnl = hist.get("realized_pl", 0.0)
        pnl_percent = hist.get("pnl_percent", 0.0)
        timestamp = hist.get("timestamp", "N/A")
        
        cost = buy_price * qty
        total_closed_cost += cost
        total_realized_pl += pnl
        
        if pnl > 0:
            win_count += 1
        elif pnl < 0:
            loss_count += 1
            
        closed_detail.append({
            "symbol": symbol,
            "market": market,
            "qty": qty,
            "sell_price": price,
            "buy_price": buy_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "timestamp": timestamp
        })
        
    total_invested = total_position_cost + total_closed_cost
    total_pnl = total_realized_pl + total_unrealized_pl
    roi = (total_unrealized_pl / total_position_cost * 100) if total_position_cost > 0 else 0.0
    overall_roi = (total_pnl / total_position_cost * 100) if total_position_cost > 0 else 0.0
    
    total_trades = win_count + loss_count
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0
    
    print(f"\n--- Portfolio Summary ---")
    print(f"Current USD/TWD Rate: {rate:.4f}")
    print(f"Active Positions Cost: {total_position_cost:,.2f} TWD")
    print(f"Realized PnL: {total_realized_pl:+,.2f} TWD")
    print(f"Unrealized PnL: {total_unrealized_pl:+,.2f} TWD")
    print(f"Total PnL (Realized + Unrealized): {total_pnl:+,.2f} TWD")
    print(f"Active Position ROI (Unrealized PnL / Active Cost): {roi:+.2f}%")
    print(f"Active Account ROI (Total PnL / Active Cost): {overall_roi:+.2f}%")
    print(f"Win Rate: {win_rate:.2f}% ({win_count} Wins / {loss_count} Losses / {total_trades} Closed Trades)")
    
    print(f"\n--- Open Positions Detail ---")
    # Sort open positions by pnl_percent descending
    open_positions_detail.sort(key=lambda x: x["pnl_percent"], reverse=True)
    for op in open_positions_detail:
        market_label = op['market']
        symbol_label = op['symbol']
        buy_label = f"${op['buy_price']:,.2f}"
        
        # Display current price
        from api.services.shioaji_service import is_usd_denominated
        if is_usd_denominated(op['symbol'], op['market']):
            usd_price = op['current_price'] / rate
            curr_label = f"{usd_price:.2f} USD (${op['current_price']:,.2f} TWD)"
        else:
            curr_label = f"${op['current_price']:,.2f} TWD"
            
        print(f"  [{market_label}] {symbol_label} | Qty: {op['qty']:.4f} | Avg Cost: {buy_label} TWD | Current: {curr_label} | Cost: {op['cost']:,.2f} TWD | PnL: {op['pnl']:+,.2f} TWD ({op['pnl_percent']:+.2f}%)")
        
    print(f"\n--- Recent Closed Trades (Last 10) ---")
    # Sort by timestamp reverse
    closed_detail.sort(key=lambda x: x["timestamp"], reverse=True)
    for cd in closed_detail[:10]:
        print(f"  {cd['timestamp'][:10]} | [{cd['market']}] {cd['symbol']} | Qty: {cd['qty']:.4f} | Buy: {cd['buy_price']:,.2f} | Sell: {cd['sell_price']:,.2f} | PnL: {cd['pnl']:+,.2f} ({cd['pnl_percent']:+.2f}%)")

if __name__ == "__main__":
    uids = ["system_auto", "system_eric", "rover.k.chen@gmail.com"]
    for uid in uids:
        try:
            analyze_user(uid)
        except Exception as e:
            print(f"Error analyzing {uid}: {e}")
            import traceback
            traceback.print_exc()
