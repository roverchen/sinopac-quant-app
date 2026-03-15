from fastapi import APIRouter, Depends, HTTPException
from api.routes.auth import get_current_user
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_credentials, update_user_credentials, get_user_trade_logs
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
        "backend_version": "1.2.2"
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
    return {"pending": [L for L in logs if L.get("entry_type") == "PENDING"]}

@router.get("/history")
async def get_trade_history(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get trade history"""
    target_user = user_id if user_id else current_user
    logs = get_user_trade_logs(target_user)
    return {"history": [L for L in logs if L.get("entry_type") == "HISTORY"]}

@router.get("/summary")
async def get_performance_summary(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """Get portfolio performance summary (P/L)"""
    target_user = user_id if user_id else current_user
    logs = get_user_trade_logs(target_user)
    positions = [L for L in logs if L.get("entry_type") == "POSITION"]
    history = [L for L in logs if L.get("entry_type") == "HISTORY"]

    realized_mock = sum(item.get('realized_pl', 0) for item in history if item.get('is_simulation') or target_user == "system_auto")
    realized_live = sum(item.get('realized_pl', 0) for item in history if not item.get('is_simulation') and target_user != "system_auto")

    unrealized_mock = 0.0
    unrealized_live = 0.0

    for pos in positions:
        current = pos.get('current_price', 0)
        buy = pos.get('buy_price', 0)
        qty = pos.get('qty', 0)
        if current and buy and qty:
            pnl = (current - buy) * qty
            if pos.get('is_simulation'):
                unrealized_mock += pnl
            else:
                unrealized_live += pnl

    return {
        "mock": {
            "realized": round(realized_mock, 2),
            "unrealized": round(unrealized_mock, 2),
            "total": round(realized_mock + unrealized_mock, 2),
            "return_rate": 0.0 # Return rate calculation depends on initial deposit, which is now 0 by default
        },
        "live": {
            "realized": round(realized_live, 2),
            "unrealized": round(unrealized_live, 2),
            "total": round(realized_live + unrealized_live, 2),
            "return_rate": 0 
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

    max_bal = {"total_twd": 0.0, "details": {}}
    try:
        creds = get_user_credentials(current_user)
        if creds.get("max_api_key") and creds.get("max_api_secret"):
            max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
            balances = max_api.get_account_balance()
            if isinstance(balances, dict) and "error" not in balances:
                twd = balances.get('twd', {}).get('balance', 0.0)
                usdt = balances.get('usdt', {}).get('balance', 0.0)
                max_bal = {
                    "twd": round(twd, 2),
                    "usdt": round(usdt, 2),
                    "total_twd_estimate": round(twd + (usdt * 32), 2)
                }
    except:
        pass

    return {
        "sinopac_twd": shioaji_bal,
        "max": max_bal
    }
@router.get("/robot_status")
async def get_robot_status(current_user: str = Depends(get_current_user)):
    """Get the current status of the automated trading robot"""
    from api.services.storage_service import get_robot_status
    return get_robot_status()
