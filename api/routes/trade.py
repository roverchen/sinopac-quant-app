from fastapi import APIRouter, Depends, HTTPException
from api.routes.auth import get_current_user
from api.services.shioaji_service import ShioajiService
from api.services.reconciliation_service import reconciliation_service
from api.services.storage_service import get_user_credentials, update_user_credentials, get_user_trade_logs
from api.services.strategy_accounts import is_system_strategy_account, list_strategy_account_ids
from api.services.quant_service import get_symbol_name
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/trade", tags=["trade"])

class OrderRequest(BaseModel):
    symbol: str
    qty: float
    price: float
    action: str = "Buy" # "Buy" or "Sell"
    is_simulation: bool = True

@router.get("/status")
async def get_trading_status(current_user: str = Depends(get_current_user)):
    """Check auto-trade status"""
    creds = get_user_credentials(current_user)
    return {
        "auto_trade_enabled": creds.get("auto_trade_enabled", False),
        "mode": "Simulation" if creds.get("simulation_mode", True) else "Live",
        "backend_version": "2.6.9"
    }

@router.post("/toggle")
async def toggle_auto_trade(enabled: bool, current_user: str = Depends(get_current_user)):
    """Toggle auto-trade on/off"""
    creds = get_user_credentials(current_user)
    creds["auto_trade_enabled"] = enabled
    update_user_credentials(current_user, creds)
    return {"message": f"Auto-trade {'enabled' if enabled else 'disabled'}"}

@router.get("/account")
async def get_account_summary(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get account summary and positions"""
    target_user = user_id if user_id else current_user
    info = ShioajiService.get_account_info(target_user)
    if not info:
        return {"status": "disconnected", "message": "API Key not set or connection failed"}

    positions = ShioajiService.get_positions(target_user)

    return {
        "status": "connected",
        "balance": ShioajiService.get_balance(target_user),
        "positions": positions
    }

@router.get("/pending")
async def get_pending_orders(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get pending orders"""
    target_user = user_id if user_id else current_user
    logs = get_user_trade_logs(target_user)
    pending = [L for L in logs if L.get("entry_type") == "PENDING"]
    
    # [v2.6.9] Robust Name Resolution
    for o in pending:
        if not o.get("name") or o.get("name") == o.get("symbol"):
            o["name"] = get_symbol_name(o.get("symbol"), o.get("market", "TW"))
            
    # Sort by timestamp (newest first)
    pending.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"pending": pending}

@router.get("/history")
async def get_trade_history(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get trade history"""
    target_user = user_id if user_id else current_user
    logs = get_user_trade_logs(target_user)
    history = [L for L in logs if L.get("entry_type") == "HISTORY" and (L.get("action") == "Sell" or L.get("status") == "CANCELLED")]
    
    # [v2.6.9] Robust Name Resolution
    for h in history:
        if not h.get("name") or h.get("name") == h.get("symbol"):
            h["name"] = get_symbol_name(h.get("symbol"), h.get("market", "TW"))

    # Sort by timestamp (newest first)
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"history": history[:20]}

@router.get("/summary")
async def get_performance_summary(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get portfolio performance summary (P/L) based on actual invested capital."""
    target_user = user_id if user_id else current_user
    logs = get_user_trade_logs(target_user)
    positions = [L for L in logs if L.get("entry_type") == "POSITION"]
    history = [L for L in logs if L.get("entry_type") == "HISTORY"]

    # Calculate PnL and Invested Capital
    realized_mock = 0.0
    realized_live = 0.0
    invested_mock = 0.0
    invested_live = 0.0

    # From Closed Trades (History)
    for item in history:
        pnl = item.get('realized_pl', 0)
        # Original Buy Cost = (Sell Price * Qty) - Fees - Tax - Realized PnL
        # This works for both manual and auto since trade_engine sets realized_pl
        buy_cost = (item.get('price', 0) * item.get('qty', 0)) - item.get('fee', 0) - item.get('tax', 0) - pnl
        
        if item.get('is_simulation') or is_system_strategy_account(target_user):
            realized_mock += pnl
            invested_mock += buy_cost
        else:
            realized_live += pnl
            invested_live += buy_cost

    unrealized_mock = 0.0
    unrealized_live = 0.0

    # From Open Positions
    for pos in positions:
        current = pos.get('current_price', 0)
        buy = pos.get('buy_price', 0)
        qty = pos.get('qty', 0)
        if current and buy and qty:
            pnl = (current - buy) * qty
            buy_cost = buy * qty
            if pos.get('is_simulation') or is_system_strategy_account(target_user):
                unrealized_mock += pnl
                invested_mock += buy_cost
            else:
                unrealized_live += pnl
                invested_live += buy_cost

    return {
        "mock": {
            "realized": round(realized_mock, 2),
            "unrealized": round(unrealized_mock, 2),
            "total": round(realized_mock + unrealized_mock, 2),
            "invested": round(invested_mock, 2),
            "return_rate": round(((realized_mock + unrealized_mock) / invested_mock * 100), 2) if invested_mock > 0 else 0.0
        },
        "live": {
            "realized": round(realized_live, 2),
            "unrealized": round(unrealized_live, 2),
            "total": round(realized_live + unrealized_live, 2),
            "invested": round(invested_live, 2),
            "return_rate": round(((realized_live + unrealized_live) / invested_live * 100), 2) if invested_live > 0 else 0.0
        }
    }

@router.post("/order")
async def place_manual_order(order: OrderRequest, current_user: str = Depends(get_current_user)):
    """Place manual order"""
    try:
        from shioaji.constant import Action
        action = Action.Buy if order.action == "Buy" else Action.Sell

        trade = ShioajiService.place_order(
            current_user,
            order.symbol,
            order.qty,
            order.price,
            action,
            is_simulation=order.is_simulation
        )
        return {"status": "success", "trade_id": str(trade.order.id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/orders")
async def get_orders(current_user: str = Depends(get_current_user)):
    """Get broker order records"""
    orders = ShioajiService.get_orders(current_user)
    return {"orders": orders}

@router.get("/balance")
async def get_combined_balance(current_user: str = Depends(get_current_user)):
    """Get combined balance (Sinopac + MAX)"""
    from api.services.storage_service import get_user_credentials
    from max_api import MaxExchangeAPI

    shioaji_bal = ShioajiService.get_balance(current_user)

    max_bal = {"twd": 0.0, "usdt": 0.0, "total_twd_estimate": 0.0}
    try:
        creds = get_user_credentials(current_user)
        if creds.get("max_api_key") and creds.get("max_api_secret"):
            from max_api import MaxExchangeAPI
            max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
            balances = max_api.get_account_balance()
            if isinstance(balances, dict) and "error" not in balances:
                twd = balances.get('twd', {}).get('balance', 0.0)
                usdt = balances.get('usdt', {}).get('balance', 0.0)
                
                # Fetch real rate if possible
                rate = 32.5
                try:
                    import yfinance as yf
                    rate_df = yf.Ticker("TWD=X").history(period="1d")
                    if not rate_df.empty:
                        rate = float(rate_df['Close'].iloc[-1])
                except: pass

                max_bal = {
                    "twd": round(twd, 2),
                    "usdt": round(usdt, 2),
                    "total_twd_estimate": round(twd + (usdt * rate), 2)
                }
    except:
        pass

    return {
        "sinopac_twd": shioaji_bal,
        "max": max_bal
    }
@router.post("/sync")
async def sync_with_broker(current_user: str = Depends(get_current_user)):
    """Force sync trade logs with real brokerage data"""
    try:
        from api.services.reconciliation_service import reconciliation_service
        result = reconciliation_service.sync_broker_data(current_user)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/robot_status")
async def get_robot_status(current_user: str = Depends(get_current_user)):
    """Get the current status of the automated trading robot"""
    from api.services.storage_service import get_robot_status
    return get_robot_status()
@router.delete("/order/{trade_id}")
@router.delete("/order/{trade_id}/")
async def cancel_order(trade_id: str, current_user: str = Depends(get_current_user)):
    """Cancel a pending order"""
    try:
        print(f"[TradeRoute] Cancellation request for {trade_id} by {current_user}")
        from api.services.trade_engine import engine
        
        # Try user's own orders first
        success = engine.cancel_order(current_user, trade_id)
        if not success:
            # Also try system strategy accounts
            for system_user in list_strategy_account_ids():
                print(f"[TradeRoute] Order {trade_id} not found for {current_user}, checking {system_user}...")
                success = engine.cancel_order(system_user, trade_id)
                if success:
                    break
            
        if success:
            print(f"[TradeRoute] Cancellation success for {trade_id}")
            return {"status": "success", "message": "Order cancelled"}
        else:
            print(f"[TradeRoute] Cancellation failed: Order {trade_id} not found after checking user and system strategy accounts")
            raise HTTPException(status_code=404, detail=f"Order {trade_id} not found or already filled")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[TradeRoute] CRITICAL ERROR during cancellation: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
