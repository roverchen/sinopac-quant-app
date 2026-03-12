import os
import threading
import random
from datetime import datetime
from typing import Dict, Optional
from api.services.storage_service import get_user_credentials

class MockShioajiClient:
    """模擬 Shioaji API 用於無憑證測試"""
    def __init__(self, user_id=None):
        self.is_mock = True
        self.user_id = user_id
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
        # 模擬模式下，訂單進入「掛單」狀態
        order_id = f"MOCK-{random.randint(1000,9999)}"
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

    def get_positions(self):
        """從儲存空間讀取模擬持倉"""
        if self.user_id:
            from api.services.storage_service import get_user_mock_positions
            return get_user_mock_positions(self.user_id)
        return []

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

            print(f"[ShioajiService] Attempting live login for {email}...")
            creds = get_user_credentials(email)
            print(f"[ShioajiService] Credentials found for {email}: {list(creds.keys())}")

            # 如果沒有憑證，直接返回 MockClient 進入模擬模式
            if not creds or 'shioaji_api_key' not in creds or not creds['shioaji_api_key']:
                print(f"[ShioajiService] Missing API keys for {email}, using MockShioajiClient.")
                mock_api = MockShioajiClient(user_id=email)
                _shioaji_instances[email] = mock_api
                return mock_api

            try:
                import shioaji as sj
                api = sj.Shioaji()
                print(f"[ShioajiService] Logging in with API Key: {creds['shioaji_api_key'][:5]}...")
                api.login(
                    api_key=creds['shioaji_api_key'],
                    secret_key=creds['shioaji_secret_key']
                )
                print(f"[ShioajiService] Login SUCCESS for {email}")
                _shioaji_instances[email] = api
                return api
            except Exception as e:
                print(f"[ShioajiService] Login FAILED for {email}: {e}")
                import traceback
                traceback.print_exc()
                mock_api = MockShioajiClient(user_id=email)
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
            return MockShioajiClient(user_id=email).place_order(None, None, symbol=symbol, qty=qty, price=price, action=str(action) if action else "Buy")

        api = cls.get_api_client(email)

        # 究極繞過邏輯：只要檢測到是 MockClient，就絕對不觸發任何 Shioaji 內部邏輯
        is_mock = False
        if api is None: is_mock = True
        elif hasattr(api, 'is_mock'): is_mock = True
        elif type(api).__name__ == 'MockShioajiClient': is_mock = True
        elif "MockShioajiClient" in str(type(api)): is_mock = True

        # 如果使用者明確要求「實盤交易」(is_simulation=False)，但我們拿到的卻是 Mock API
        # 則不應該默默轉模擬，而是要報錯讓使用者知道 API Key 有問題
        if is_simulation == False and is_mock:
            raise Exception(f"[ShioajiService] 實盤交易失敗：無法連線至永豐 API。請檢查您的 API Key 與 Secret 是否正確。")

        if is_mock:
            print(f"DEBUG: [v1.0.3] Auto Mock Triggered for {email}")
            # 模擬模式下，所有下單進入掛單佇列，由 TradeEngine 進行價格撮合
            from api.services.storage_service import get_user_pending_orders, save_user_pending_orders
            pending = get_user_pending_orders(email)
            order_id = f"MOCK-{random.randint(1000,9999)}"

            # 判斷市場
            market = "TW"
            if symbol.isdigit() and len(symbol) >= 4: market = "TW"
            elif any(c.isalpha() for c in symbol):
                if "-" in symbol or "USD" in symbol: market = "CRYPTO"
                else: market = "US"

            pending.append({
                "trade_id": order_id,
                "symbol": symbol,
                "action": "Buy" if "Buy" in str(action) else "Sell",
                "qty": qty,
                "price": price,
                "market": market,
                "is_simulation": True,
                "timestamp": datetime.now().isoformat()
            })
            save_user_pending_orders(email, pending)

            class MockTrade:
                class Order: id = order_id
                order = Order()
            return MockTrade()

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

        # 進入掛單追蹤系統
        from api.services.storage_service import get_user_pending_orders, save_user_pending_orders
        pending = get_user_pending_orders(email)
        pending.append({
            "trade_id": str(trade.order.id),
            "symbol": symbol,
            "action": "Buy" if action == Action.Buy else "Sell",
            "qty": qty,
            "price": price,
            "market": "TW",
            "is_simulation": False,
            "timestamp": datetime.now().isoformat()
        })
        save_user_pending_orders(email, pending)

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

    @classmethod
    def get_positions(cls, email: str):
        """
        取得當前持倉。
        """
        api = cls.get_api_client(email)
        if not api: return []

        # 處理模擬模式
        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            positions = api.get_positions()
        else:
            try:
                # 實務上 Shioaji 查詢庫存
                pos_list = api.list_positions(api.list_accounts()[0])
                positions = []
                for p in pos_list:
                    positions.append({
                        "symbol": p.code,
                        "qty": p.quantity,
                        "buy_price": p.price,
                        "market": "TW", # 預設台股，可擴展
                        "is_simulation": False
                    })
            except Exception as e:
                print(f"Error fetching real positions: {e}")
                positions = []

        # 注入目前價格與損益試算
        from api.services.quant_service import get_yahoo_ticker, fetch_stock_data
        for p in positions:
            try:
                ticker = get_yahoo_ticker(p['symbol'], p['market'])
                df = fetch_stock_data(p['symbol'], ticker, period="1d")
                if df is not None and not df.empty:
                    current_price = round(float(df['Close'].iloc[-1]), 2)
                    p['current_price'] = current_price
                    p['pnl_percent'] = round(((current_price - p['buy_price']) / p['buy_price']) * 100, 2)
                else:
                    p['current_price'] = p['buy_price']
                    p['pnl_percent'] = 0.0
            except:
                p['current_price'] = p['buy_price']
                p['pnl_percent'] = 0.0

        return positions

# 全域單例
shioaji_service = ShioajiService()
