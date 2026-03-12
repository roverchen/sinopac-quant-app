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
async def get_account_summary(current_user: str = Depends(get_current_user)):
    """取得庫存與資金概況"""
    info = ShioajiService.get_account_info(current_user)
    if not info:
        return {"status": "disconnected", "message": "API Key 未設定或連線失敗"}
    
    positions = ShioajiService.get_positions(current_user)
    
    return {
        "status": "connected",
        "balance": 1000000, # 可進一步串接餘額查詢
        "positions": positions
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
