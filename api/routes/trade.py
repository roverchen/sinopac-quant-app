from fastapi import APIRouter, Depends, HTTPException
from api.routes.auth import get_current_user
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_credentials, update_user_credentials
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
    """查詢自動交易開關狀態"""
    creds = get_user_credentials(current_user)
    return {
        "auto_trade_enabled": creds.get("auto_trade_enabled", False),
        "mode": "Simulation" if creds.get("simulation_mode", True) else "Live",
        "backend_version": "1.0.2"
    }

@router.post("/toggle")
async def toggle_auto_trade(enabled: bool, current_user: str = Depends(get_current_user)):
    """開啟或關閉自動交易"""
    creds = get_user_credentials(current_user)
    creds["auto_trade_enabled"] = enabled
    update_user_credentials(current_user, creds)
    return {"message": f"Auto-trade {'enabled' if enabled else 'disabled'}"}

@router.get("/account")
async def get_account_summary(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """取得庫存與資金概況"""
    target_user = user_id if user_id else current_user
    info = ShioajiService.get_account_info(target_user)
    if not info:
        return {"status": "disconnected", "message": "API Key 未設定或連線失敗"}
    
    positions = ShioajiService.get_positions(target_user)
    
    return {
        "status": "connected",
        "balance": 1000000,
        "positions": positions
    }

@router.get("/pending")
async def get_pending_orders(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """取得待成交訂單"""
    from api.services.storage_service import get_user_pending_orders
    target_user = user_id if user_id else current_user
    pending = get_user_pending_orders(target_user)
    return {"pending": pending}

@router.get("/history")
async def get_trade_history(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """取得交易歷史紀錄"""
    from api.services.storage_service import get_user_trade_history
    target_user = user_id if user_id else current_user
    history = get_user_trade_history(target_user)
    return {"history": history}

@router.get("/summary")
async def get_performance_summary(user_id: Optional[str] = None, current_user: str = Depends(get_current_user)):
    """取得投資績效總計 (P/L)"""
    from api.services.storage_service import get_user_trade_history
    target_user = user_id if user_id else current_user
    positions = ShioajiService.get_positions(target_user)
    history = get_user_trade_history(target_user)
    
    # 系統機器人歷史皆視為模擬
    realized_mock = sum(item.get('realized_pnl', 0) for item in history if item.get('is_simulation') or target_user == "system_auto")
    realized_live = sum(item.get('realized_pnl', 0) for item in history if not item.get('is_simulation') and target_user != "system_auto")
    
    unrealized_mock = 0.0
    unrealized_live = 0.0
    
    for pos in positions:
        # P/L 試算是在 get_positions 中注入的
        # pos['pnl_percent'] 是百分比，我們需要絕對值
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
            "return_rate": round((realized_mock + unrealized_mock) / 1000000 * 100, 2) if realized_mock + unrealized_mock != 0 else 0
        },
        "live": {
            "realized": round(realized_live, 2),
            "unrealized": round(unrealized_live, 2),
            "total": round(realized_live + unrealized_live, 2),
            "return_rate": 0 # 實盤回報率需根據實際本金計算
        }
    }

@router.post("/order")
async def place_manual_order(order: OrderRequest, current_user: str = Depends(get_current_user)):
    """手動下單介面"""
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
    """取得委託紀錄"""
    orders = ShioajiService.get_orders(current_user)
    return {"orders": orders}
