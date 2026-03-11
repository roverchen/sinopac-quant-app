import shioaji as sj
from shioaji import Order
from shioaji.constant import Action, StockPriceType, OrderType
import os
import threading
from typing import Dict, Optional
from api.services.storage_service import get_user_credentials

class ShioajiService:
    _instance_lock = threading.Lock()
    _instances: Dict[str, sj.Shioaji] = {}

    @classmethod
    def get_api_client(cls, email: str) -> Optional[sj.Shioaji]:
        """
        為特定使用者取得或建立 Shioaji API 實例（Singleton per user）。
        """
        with cls._instance_lock:
            if email in cls._instances:
                # 簡單檢查是否還在登入狀態（這裡 shioaji 沒有直接的 is_connected，通常靠呼叫測試）
                return cls._instances[email]

            creds = get_user_credentials(email)
            if not creds or 'shioaji_api_key' not in creds:
                return None

            try:
                api = sj.Shioaji()
                api.login(
                    api_key=creds['shioaji_api_key'],
                    secret_key=creds['shioaji_secret_key']
                )
                cls._instances[email] = api
                return api
            except Exception as e:
                print(f"Shioaji login failed for {email}: {e}")
                return None

    @classmethod
    def place_order(cls, email: str, symbol: str, qty: int, price: float, action: Action = Action.Buy):
        """
        執行下單操作。
        """
        api = cls.get_api_client(email)
        if not api:
            raise Exception("無法取得 API 連線，請檢查憑證設定。")

        # 找尋合約
        contract = None
        for mk in ["TSE", "OTC"]:
            try:
                contract = getattr(api.Contracts.Stocks, mk)[symbol]
                if contract: break
            except: continue

        if not contract:
            raise Exception(f"找不到標的 {symbol} 的合約。")

        order = Order(
            price=price,
            quantity=qty,
            action=action,
            price_type=StockPriceType.LMT,
            order_type=OrderType.ROD,
            account=api.list_accounts()[0]
        )

        trade = api.place_order(contract, order)
        return trade

    @classmethod
    def get_account_info(cls, email: str):
        """
        取得資金與庫存資訊。
        """
        api = cls.get_api_client(email)
        if not api:
            return None
        
        try:
            accounts = api.list_accounts()
            if not accounts:
                return None
            
            # 這裡簡化回傳第一個帳號的概況
            # 實務上 Shioaji 查詢庫存與資金需要點時間
            return {
                "account_id": accounts[0].account_id,
                "status": "connected"
            }
        except:
            return None

# 全域單例
shioaji_service = ShioajiService()
