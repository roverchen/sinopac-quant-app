import os
import threading
import random
from datetime import datetime
from typing import Dict, Optional
from api.services.storage_service import get_user_credentials, get_user_trade_logs, save_user_trade_logs

class MockShioajiClient:
    """Mock Shioaji API for testing without credentials"""
    def __init__(self, user_id=None):
        self.is_mock = True
        self.user_id = user_id
        self.Contracts = self
        self.Stocks = self
        self.TSE = self
        self.OTC = self
        self._mock_orders = [] 

    def __getitem__(self, key): return self
    def list_accounts(self):
        class MockAcc: account_id = "MOCK-PAPER-TRADING-001"
        return [MockAcc()]

    def place_order(self, contract, order, symbol=None, qty=None, price=None, action=None, name=None):
        logs = get_user_trade_logs(self.user_id)
        order_id = f"SIM-{random.randint(1000,9999)}"
        
        target_symbol = symbol or (contract.code if contract else "Unknown")
        target_qty = qty or (order.quantity if order else 0)
        target_price = price or (order.price if order else 0)
        target_action = action or (str(order.action) if order else "Buy")

        # Market detection
        c = target_symbol.upper()
        if target_symbol.isdigit() and len(target_symbol) >= 4:
            market = "TW"
        elif "-" in c or c.endswith("USDT") or c.endswith("TWD"):
            market = "CRYPTO"
        else:
            market = "US"

        logs.append({
            "trade_id": order_id,
            "symbol": target_symbol,
            "name": name or target_symbol, # Persist name if provided
            "action": "Buy" if "Buy" in str(target_action) else "Sell",
            "qty": float(target_qty),
            "price": float(target_price),
            "market": market,
            "is_simulation": True,
            "entry_type": "PENDING",
            "status": "OPEN",
            "timestamp": datetime.now().isoformat()
        })
        save_user_trade_logs(self.user_id, logs)
        print(f"[MockShioaji] SIM Order saved for {self.user_id}: {target_symbol} @ {target_price}")

        class MockTrade:
            class Order: id = order_id
            order = Order()
        return MockTrade()

    def get_orders(self):
        if not self._mock_orders:
            self._mock_orders = [
                {"trade_id": "MOCK-0001", "symbol": "2330", "action": "Buy", "qty": 1, "price": 1025.0, "status": "FILLED", "time": "2026-03-11"}
            ]
        return self._mock_orders

    def get_positions(self):
        if self.user_id:
            logs = get_user_trade_logs(self.user_id)
            return [L for L in logs if L.get("entry_type") == "POSITION"]
        return []

_shioaji_instances = {}
_shioaji_lock = threading.Lock()

class ShioajiService:
    @classmethod
    def get_api_client(cls, email: str):
        with _shioaji_lock:
            if email in _shioaji_instances:
                return _shioaji_instances[email]

            print(f"[ShioajiService] Attempting live login for {email}...")
            creds = get_user_credentials(email)
            print(f"[ShioajiService] Credentials found for {email}: {list(creds.keys())}")

            if not creds or 'shioaji_api_key' not in creds or not creds['shioaji_api_key']:
                print(f"[ShioajiService] Missing API keys for {email}, using MockShioajiClient.")
                mock_api = MockShioajiClient(user_id=email)
                _shioaji_instances[email] = mock_api
                return mock_api

            try:
                import shioaji as sj
                api = sj.Shioaji()
                print(f"[ShioajiService] Logging in with API Key: {creds['shioaji_api_key'][:5]}...")
                
                # Preferred login with Person ID if available for real trading
                login_kwargs = {
                    "api_key": creds['shioaji_api_key'],
                    "secret_key": creds['shioaji_secret_key']
                }
                
                api.login(**login_kwargs)
                
                # Activate CA if certificate exists
                if creds.get('shioaji_ca_base64') and creds.get('shioaji_ca_password'):
                    try:
                        import base64
                        ca_content = base64.b64decode(creds['shioaji_ca_base64'])
                        ca_path = f"/tmp/ca_{creds.get('shioaji_person_id', 'user')}.pfx"
                        with open(ca_path, 'wb') as f:
                            f.write(ca_content)
                        
                        print(f"[ShioajiService] Activating CA for {email}...")
                        api.activate_ca(
                            ca_path=ca_path,
                            ca_passwd=creds['shioaji_ca_password'],
                            person_id=creds.get('shioaji_person_id')
                        )
                        print(f"[ShioajiService] CA Activation SUCCESS for {email}")
                    except Exception as ca_e:
                        print(f"[ShioajiService] CA Activation FAILED: {ca_e}")

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
    def place_order(cls, email: str, symbol: str, qty: float, price: float, action=None, is_simulation: bool = None, name: str = None):
        if is_simulation is True:
            print(f"DEBUG: Forced Simulation Mode for {email}")
            return MockShioajiClient(user_id=email).place_order(None, None, symbol=symbol, qty=qty, price=price, action=str(action) if action else "Buy", name=name)

        api = cls.get_api_client(email)

        def get_symbol_name(symbol_code, market_type):
            try:
                from api.services.quant_service import fetch_tw_symbols, fetch_us_symbols, fetch_crypto_symbols
                if market_type == "TW":
                    s_map = fetch_tw_symbols()
                elif market_type == "US":
                    s_map = fetch_us_symbols()
                else:
                    s_map = fetch_crypto_symbols()
                return s_map.get(symbol_code, symbol_code)
            except:
                return symbol_code

        is_mock = False
        if api is None: is_mock = True
        elif hasattr(api, 'is_mock'): is_mock = True
        elif type(api).__name__ == 'MockShioajiClient': is_mock = True
        elif "MockShioajiClient" in str(type(api)): is_mock = True

        if is_simulation == False and is_mock:
            raise Exception(f"[ShioajiService] Live trading failed: Unable to connect to Sinopac API. Please check your credentials.")

        if is_mock:
            logs = get_user_trade_logs(email)
            order_id = f"MOCK-{random.randint(1000,9999)}"

            # Detect market
            c = symbol.upper()
            if symbol.isdigit() and len(symbol) >= 4:
                market = "TW"
            elif "-" in c or c.endswith("USDT") or c.endswith("TWD"):
                market = "CRYPTO"
            else:
                market = "US"

            pending_item = {
                "trade_id": order_id,
                "symbol": symbol,
                "name": get_symbol_name(symbol, market),
                "action": "Buy" if "Buy" in str(action) else "Sell",
                "qty": float(qty),
                "price": float(price),
                "market": market,
                "is_simulation": True,
                "entry_type": "PENDING",
                "status": "OPEN",
                "timestamp": datetime.now().isoformat(),
                "order_time": datetime.now().isoformat()
            }
            logs.append(pending_item)
            save_user_trade_logs(email, logs)
            print(f"[ShioajiService] MOCK Order saved for {email}: {symbol} @ {price}")

            class MockTrade:
                class Order: id = order_id
                order = Order()
            return MockTrade()

        from shioaji.constant import Action, StockPriceType, OrderType
        from shioaji import Order

        if action is None:
            action = Action.Buy

        if not api:
            raise Exception("Unable to establish API connection.")

        # Strip market prefix if it exists (e.g. CRYPTO:BTC-USD -> BTC-USD)
        clean_symbol = symbol
        if ":" in symbol:
            clean_symbol = symbol.split(":", 1)[1]

        # Detect market
        c = clean_symbol.upper()
        market = "US"
        if clean_symbol.isdigit() and len(clean_symbol) >= 4:
            market = "TW"
        elif "-" in c or c.endswith("USDT") or c.endswith("TWD") or c in ["BTC", "ETH", "SOL"]:
            market = "CRYPTO"

        if market == "CRYPTO":
            # Crypto Live Trading via MAX API
            try:
                from max_api import MaxExchangeAPI
                creds = get_user_credentials(email)
                if not creds.get("max_api_key") or not creds.get("max_api_secret"):
                    raise Exception("MAX API Keys missing for live crypto trading.")
                
                max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                # MAX integration: needs specific side and market
                side = "buy" if "Buy" in str(action) else "sell"
                
                # Robust symbol conversion for MAX (e.g. BTC-USD -> btcusdt)
                m_symbol = clean_symbol.lower().replace("-", "")
                
                # [v2.1.43] MATIC renamed to POL on MAX
                if "matic" in m_symbol:
                    print(f"[ShioajiService] Mapping MATIC to POL for MAX compatibility: {m_symbol} -> {m_symbol.replace('matic', 'pol')}")
                    m_symbol = m_symbol.replace('matic', 'pol')
                
                # [v2.1.62] Handle TWD/USD/USDT suffix safely (Prioritize TWD)
                if m_symbol.endswith("usd"):
                    m_symbol = m_symbol[:-3] + "twd"
                elif m_symbol.endswith("usdt"):
                    m_symbol = m_symbol[:-4] + "twd"
                elif not m_symbol.endswith("twd"):
                    m_symbol += "twd"
                
                print(f"[MAX] Placing {side} order for {m_symbol} qty {qty} @ {price}")
                # [FIX] Use place_order as defined in max_api.py
                res = max_api.place_order(m_symbol, side, qty, price)
                
                if "error" in res:
                    raise Exception(f"MAX API Error: {res['error']}")

                trade_id = str(res.get('id'))
                if not trade_id or trade_id == "None":
                    raise Exception(f"MAX API returned no order ID. Response: {res}")
                
                # Log to unified logs
                logs = get_user_trade_logs(email)
                logs.append({
                    "trade_id": trade_id,
                    "symbol": symbol,
                    "name": get_symbol_name(symbol, "CRYPTO"),
                    "action": "Buy" if side == "buy" else "Sell",
                    "qty": qty,
                    "price": price,
                    "market": "CRYPTO",
                    "is_simulation": False,
                    "entry_type": "PENDING",
                    "status": "OPEN",
                    "timestamp": datetime.now().isoformat(),
                    "order_time": datetime.now().isoformat()
                })
                save_user_trade_logs(email, logs)
                
                class MockTrade:
                    class Order: id = trade_id
                    order = Order()
                return MockTrade()
            except Exception as e:
                print(f"[ShioajiService] Crypto Live Error: {e}")
                raise e

        # Shioaji Live Trading (TW & US)
        from shioaji.constant import Action, StockPriceType, OrderType
        from shioaji import Order

        if action is None:
            action = Action.Buy

        if not api:
            raise Exception("Unable to establish Shioaji API connection.")

        contract = None
        if market == "TW":
            for mk in ["TSE", "OTC"]:
                try:
                    contract = getattr(api.Contracts.Stocks, mk)[symbol]
                    if contract: break
                except: continue
        else: # US Sub-brokerage
            try:
                contract = api.Contracts.USA[symbol]
            except Exception as e:
                print(f"[ShioajiService] US Contract lookup failed for {symbol}: {e}")

        if not contract:
            raise Exception(f"Unable to find {market} contract for {symbol}. Verify symbol or use Simulation mode.")

        # Shioaji Order
        order = Order(
            price=price,
            quantity=qty,
            action=action,
            price_type=StockPriceType.LMT,
            order_type=OrderType.ROD,
            account=api.list_accounts()[0]
        )

        trade = api.place_order(contract, order)
        
        # [FIX] Check for immediate rejection
        status_str = str(trade.status.status)
        order_id = str(trade.order.id)
        
        print(f"[ShioajiService] Live order result for {symbol}: ID={order_id}, Status={status_str}")
        
        if "Rejected" in status_str or "Failed" in status_str or not order_id:
             error_msg = getattr(trade.status, 'status_code', 'Unknown Error')
             detail_msg = getattr(trade.status, 'msg', getattr(trade.status, 'detail', ''))
             
             # [v2.1.67] Extract hidden Shioaji API JSON errors from logger output or __dict__ if available
             if not detail_msg or detail_msg == "None":
                 import json
                 try:
                     # Shioaji might bury the detail in the raw json string of the status
                     status_dict = trade.status.__dict__
                     if 'msg' in status_dict and status_dict['msg']:
                         detail_msg = str(status_dict['msg'])
                     else:
                         detail_msg = "Account Not Acceptable OR Balance Insufficient."
                 except:
                     detail_msg = "Unknown Shioaji Rejection Reason"
                     
             detail = f"Broker Rejected: {status_str} ({detail_msg})"
             raise Exception(detail)

        logs = get_user_trade_logs(email)
        logs.append({
            "trade_id": order_id,
            "symbol": symbol,
            "name": get_symbol_name(symbol, market),
            "action": "Buy" if action == Action.Buy else "Sell",
            "qty": qty,
            "price": price,
            "market": market,
            "is_simulation": False,
            "entry_type": "PENDING",
            "status": "OPEN",
            "timestamp": datetime.now().isoformat(),
            "order_time": datetime.now().isoformat()
        })
        save_user_trade_logs(email, logs)

        return trade

    @classmethod
    def get_account_info(cls, email: str):
        api = cls.get_api_client(email)
        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            return {
                "account_id": "MOCK-PAPER-001",
                "status": "connected",
                "is_mock": True
            }

        if not api: return None

        try:
            accounts = api.list_accounts()
            if not accounts: return None
            return {
                "account_id": accounts[0].account_id,
                "status": "connected"
            }
        except:
            return None

    @classmethod
    def get_balance(cls, email: str):
        # 1. Start with Shioaji balance
        shioaji_balance = 0.0
        api = cls.get_api_client(email)
        if api and not (hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient'):
            try:
                balance_data = api.account_balance()
                if balance_data and hasattr(balance_data, 'acc_balance'):
                    shioaji_balance = float(balance_data.acc_balance)
            except Exception as e:
                print(f"[ShioajiService] Shioaji balance error: {e}")
        
        # 2. Add MAX TWD balance
        max_twd_balance = 0.0
        from api.services.storage_service import get_user_credentials
        creds = get_user_credentials(email)
        if creds.get("max_api_key"):
            try:
                from max_api import MaxExchangeAPI
                max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                balances = max_api.get_account_balance()
                if "twd" in balances:
                    max_twd_balance = float(balances["twd"].get("balance", 0))
            except Exception as e:
                print(f"[ShioajiService] MAX balance error: {e}")
                
        return shioaji_balance + max_twd_balance

    @classmethod
    def get_orders(cls, email: str):
        api = cls.get_api_client(email)
        if not api: return []

        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            return api.get_orders()

        try:
            api.update_status()
            trades = api.list_trades()
            results = []
            for t in trades:
                results.append({
                    "trade_id": str(t.order.id),
                    "symbol": t.contract.code,
                    "action": str(t.order.action),
                    "qty": t.order.quantity,
                    "price": t.order.price,
                    "status": str(t.status.status),
                    "time": str(t.status.order_datetime) if hasattr(t.status, 'order_datetime') else "Unknown"
                })
            return results
        except Exception as e:
            print(f"Error fetching orders: {e}")
            return []
    @classmethod
    def get_broker_trades(cls, email: str):
        """獲取券商成交紀錄 (Real trades only)"""
        api = cls.get_api_client(email)
        if not api or hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            return []

        try:
            api.update_status()
            trades = api.list_trades()
            # Filter for FILLED or partially filled trades
            return [t for t in trades if "Filled" in str(t.status.status)]
        except Exception as e:
            print(f"Error fetching broker trades: {e}")
            return []

    @classmethod
    def cancel_order(cls, email: str, trade_id: str):
        api = cls.get_api_client(email)
        if not api or hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            return True # Mock always succeeds

        try:
            # Need to find the trade object from shioaji
            api.update_status()
            trades = api.list_trades()
            target_trade = next((t for t in trades if str(t.order.id) == str(trade_id)), None)
            
            if target_trade:
                api.cancel_order(target_trade)
                return True
            return False
        except Exception as e:
            print(f"[ShioajiService] Cancel failed for {trade_id}: {e}")
            raise e

    @classmethod
    def get_positions(cls, email: str):
        api = cls.get_api_client(email)
        if not api: return []

        if hasattr(api, 'is_mock') or type(api).__name__ == 'MockShioajiClient':
            positions = api.get_positions()
        else:
            try:
                pos_list = api.list_positions(api.list_accounts()[0])
                positions = []
                for p in pos_list:
                    positions.append({
                        "symbol": p.code,
                        "qty": p.quantity,
                        "buy_price": p.price,
                        "market": "TW",
                        "is_simulation": False
                    })
            except Exception as e:
                print(f"Error fetching real positions: {e}")
                positions = []

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

        # [v2.1.65] Join with trade_logs to get buy timestamps
        from api.services.storage_service import get_user_trade_logs
        logs = get_user_trade_logs(email)
        
        for p in positions:
            # Find the MOST RECENT 'Buy' trade for this symbol that is FILLED
            buy_record = next((L for L in reversed(logs) if L.get("symbol") == p["symbol"] and L.get("action") == "Buy" and L.get("status") == "FILLED"), None)
            
            if buy_record:
                p["buy_order_time"] = buy_record.get("order_time") or buy_record.get("timestamp")
                p["buy_filled_time"] = buy_record.get("fill_time") or buy_record.get("timestamp")
            else:
                # [v2.1.66] Fallback for legacy positions without explicit buy records
                fallback_time = None
                if p.get("trade_id") and str(p.get("trade_id")).startswith("POS-"):
                    try:
                        ts = int(str(p["trade_id"]).split("-")[1])
                        from datetime import datetime
                        fallback_time = datetime.fromtimestamp(ts).isoformat()
                    except:
                        pass
                
                if not fallback_time and p.get("timestamp"):
                    fallback_time = p.get("timestamp")
                    
                if fallback_time:
                    p["buy_order_time"] = p.get("buy_order_time") or fallback_time
                    p["buy_filled_time"] = p.get("buy_filled_time") or fallback_time

        # [v2.1.69] Inject MAX crypto holdings into positions
        from api.services.storage_service import get_user_credentials
        creds = get_user_credentials(email)
        if creds.get("max_api_key"):
            try:
                # Fetch exchange rate for conversion if needed
                exchange_rate = 1.0
                try:
                    import yfinance as yf
                    rate_df = yf.Ticker("TWD=X").history(period="1d")
                    if not rate_df.empty:
                        exchange_rate = float(rate_df['Close'].iloc[-1])
                except: pass

                from max_api import MaxExchangeAPI
                max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                balances = max_api.get_account_balance()
                for curr, detail in balances.items():
                    if curr.lower() == "twd": continue
                    qty = float(detail.get("balance", 0)) + float(detail.get("locked", 0))
                    if qty > 0:
                        symbol = f"{curr.upper()}-TWD"
                        # Check if already exists (might have been added via mock or sync)
                        if any(pos.get("symbol") == symbol for pos in positions):
                            continue
                            
                        # Try to find cost basis from trade_logs (recent FILLED Buy)
                        buy_record = next((L for L in reversed(logs) if L.get("symbol") == symbol and L.get("action") == "Buy" and L.get("status") == "FILLED"), None)
                        buy_price = float(buy_record.get("price", 0)) if buy_record else 0.0
                        
                        # Fetch current price via Yahoo
                        ticker = get_yahoo_ticker(symbol, "CRYPTO")
                        current_price_twd = buy_price
                        try:
                            df = fetch_stock_data(symbol, ticker, period="1d")
                            if df is not None and not df.empty:
                                raw_price = float(df['Close'].iloc[-1])
                                # Most Crypto on Yahoo are in USD, convert to TWD
                                current_price_twd = round(raw_price * exchange_rate, 2)
                        except: pass
                        
                        positions.append({
                            "symbol": symbol,
                            "qty": qty,
                            "buy_price": buy_price,
                            "market": "CRYPTO",
                            "is_simulation": False,
                            "current_price": current_price_twd,
                            "pnl_percent": round(((current_price_twd - buy_price) / buy_price * 100), 2) if buy_price > 0 else 0.0,
                            "buy_order_time": buy_record.get("order_time") if buy_record else None,
                            "buy_filled_time": buy_record.get("fill_time") if buy_record else None
                        })
            except Exception as e:
                print(f"[ShioajiService] MAX positions injection error: {e}")

        return positions

shioaji_service = ShioajiService()
