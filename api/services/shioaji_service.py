import os
import threading
import random
from datetime import datetime
from typing import Dict, Optional
from api.services.storage_service import get_user_credentials

class MockShioajiClient:
    """模擬 Shioaji API 用於無憑證測試"""
    def __init__(self):
        self.is_mock = True
        self.Contracts = self
        self.Stocks = self
        self.TSE = self
        self.OTC = self
        self._mock_orders = [] # 儲存模擬訂單
    
    def __getitem__(self, key): return self
    def list_accounts(self):
        class MockAcc: account_id = "MOCK-PAPER-TRADING-001"
        return [MockAcc()]
    
    def place_order(self, contract, order, symbol="2330", qty=1, price=500.0, action="Buy"):
        # 建立一個較完整的模擬訂單物件
        order_id = f"MOCK-{random.randint(1000,9999)}"
        new_order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "qty": qty,
            "price": price,
            "status": "Filled",
            "time": datetime.now().strftime("%H:%M:%S")
        }
        self._mock_orders.insert(0, new_order)
        
        class MockTrade: 
            class Order: id = order_id
            order = Order()
        return MockTrade()

    def get_orders(self):
        # 如果還沒有訂單，給一個初始範例
        if not self._mock_orders:
            self._mock_orders = [
                {"order_id": "MOCK-0001", "symbol": "2330", "action": "Buy", "qty": 1, "price": 1025.0, "status": "Filled", "time": "2026-03-11"}
            ]
        return self._mock_orders

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
    def place_order(cls, email: str, symbol: str, qty: float, price: float, action=None, is_simulation: bool = None):
        """
        執行下單操作 (v1.0.3 支援強制模擬版)。
        """
        # 如果使用者在前端明確選擇「模擬下單」，則強制走 Mock 邏輯
        if is_simulation is True:
            print(f"DEBUG: [v1.0.3] Forced Simulation Mode for {email}")
            return MockShioajiClient().place_order(None, None, symbol=symbol, qty=qty, price=price, action=str(action) if action else "Buy")

        api = cls.get_api_client(email)
        
        # 究極繞過邏輯：只要檢測到是 MockClient，就絕對不觸發任何 Shioaji 內部邏輯
        is_mock = False
        if api is None: is_mock = True
        elif hasattr(api, 'is_mock'): is_mock = True
        elif type(api).__name__ == 'MockShioajiClient': is_mock = True
        elif "MockShioajiClient" in str(type(api)): is_mock = True
        
        if is_mock:
            print(f"DEBUG: [v1.0.3] Auto Mock Triggered for {email}")
            target_api = api if api else MockShioajiClient()
            return target_api.place_order(None, None, symbol=symbol, qty=qty, price=price, action=str(action) if action else "Buy")

        from shioaji.constant import Action, StockPriceType, OrderType
        from shioaji import Order
        
        if action is None:
            action = Action.Buy
            
        if not api:
            raise Exception("[v1.0.2] 無法取得 API 連線。")

        # 找尋合約
        contract = None
        for mk in ["TSE", "OTC"]:
            try:
                contract = getattr(api.Contracts.Stocks, mk)[symbol]
                if contract: break
            except: continue

        if not contract:
            raise Exception(f"[v1.0.2] 找不到標的 {symbol} 的合約。")

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
        # 使用多重檢查以防止 isinstance 在模組重載時失敗
        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
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

    @classmethod
    def get_orders(cls, email: str):
        """
        取得委託紀錄。
        """
        api = cls.get_api_client(email)
        if not api: return []
        
        # 處理模擬模式
        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            return api.get_orders()
            
        try:
            # 實務上 Shioaji 查詢委託需要一點處理
            api.update_status()
            trades = api.list_trades()
            results = []
            for t in trades:
                results.append({
                    "order_id": str(t.order.id),
                    "symbol": t.contract.code,
                    "action": str(t.order.action),
                    "qty": t.order.quantity,
                    "price": t.order.price,
                    "status": str(t.status.status),
                    "time": str(t.status.order_datetime) if hasattr(t.status, 'order_datetime') else "未知"
                })
            return results
        except Exception as e:
            print(f"Error fetching orders: {e}")
            return []

# 全域單例
shioaji_service = ShioajiService()
