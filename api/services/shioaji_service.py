import os
import threading
import random
from typing import Dict, Optional
from api.services.storage_service import get_user_credentials

class MockShioajiClient:
    """模擬 Shioaji API 用於無憑證測試"""
    def __init__(self):
        self.Contracts = self
        self.Stocks = self
        self.TSE = self
        self.OTC = self
    
    def __getitem__(self, key): return self
    def list_accounts(self):
        class MockAcc: account_id = "MOCK-PAPER-TRADING-001"
        return [MockAcc()]
    
    def place_order(self, contract, order):
        class MockTrade: 
            class Order: id = f"MOCK-{random.randint(1000,9999)}"
            order = Order()
        return MockTrade()

# 全域變數以避免 Class Attribute 查找問題
_shioaji_instances = {}
_shioaji_lock = threading.Lock()

class ShioajiService:
    @classmethod
    def get_api_client(cls, email: str):
        """
        為特定使用者取得或建立 Shioaji API 實例（Singleton per user）。
        """
        with _shioaji_lock:
            if email in _shioaji_instances:
                return _shioaji_instances[email]

            creds = get_user_credentials(email)
            
            # 如果沒有憑證，直接返回 MockClient 進入模擬模式
            if not creds or 'shioaji_api_key' not in creds:
                print(f"No credentials for {email}, returning MockShioajiClient for simulation.")
                mock_api = MockShioajiClient()
                _shioaji_instances[email] = mock_api
                return mock_api

            try:
                import shioaji as sj
                api = sj.Shioaji()
                api.login(
                    api_key=creds['shioaji_api_key'],
                    secret_key=creds['shioaji_secret_key']
                )
                _shioaji_instances[email] = api
                return api
            except Exception as e:
                print(f"Shioaji login failed for {email}, falling back to MOCK: {e}")
                mock_api = MockShioajiClient()
                _shioaji_instances[email] = mock_api
                return mock_api

    @classmethod
    def place_order(cls, email: str, symbol: str, qty: int, price: float, action=None):
        """
        執行下單操作。
        """
        from shioaji.constant import Action, StockPriceType, OrderType
        from shioaji import Order
        
        if action is None:
            action = Action.Buy
            
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

        if not contract and not isinstance(api, MockShioajiClient):
            raise Exception(f"找不到標的 {symbol} 的合約。")

        # 如果是模擬模式，直接調用 mock 的 place_order，跳過 Order 物件的驗證
        if isinstance(api, MockShioajiClient):
            return api.place_order(None, None)

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
        if isinstance(api, MockShioajiClient):
            return {
                "account_id": "MOCK-PAPER-001",
                "status": "connected",
                "is_mock": True
            }
        
        if not api: return None
        
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
