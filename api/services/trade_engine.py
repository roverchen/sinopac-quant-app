import time
import threading
from datetime import datetime
import yfinance as yf
from api.services.storage_service import (
    get_user_trade_logs,
    save_user_trade_logs
)
from api.services.quant_service import get_yahoo_ticker
from api.services.strategy_accounts import list_strategy_account_ids

class MatchingEngine:
    def __init__(self):
        self.running = False
        self.thread = None
        self.interval = 30 # Check every 30 seconds

    def start(self):
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            print("[TradeEngine] Matching Engine started.")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

    def _run(self):
        while self.running:
            try:
                self._process_all_users()
            except Exception as e:
                print(f"[TradeEngine] Error: {e}")
            time.sleep(self.interval)

    def _process_all_users(self):
        from api.services.storage_service import get_all_users_with_pending
        active_users = get_all_users_with_pending()
        
        for system_user in list_strategy_account_ids():
            if system_user not in active_users:
                active_users.append(system_user)
            
        for user_id in active_users:
            self._check_pending_orders(user_id)

    def _check_pending_orders(self, user_id):
        # 1. Fetch logs once at the start
        logs = get_user_trade_logs(user_id)
        pending = [L for L in logs if L.get("entry_type") == "PENDING"]
        if not pending:
            return

        modified = False
        symbols = list(set([o['symbol'] for o in pending]))
        tickers = {s: get_yahoo_ticker(s, next(o['market'] for o in pending if o['symbol'] == s)) for s in symbols}

        prices = {}
        has_sim = any(o.get('is_simulation', True) for o in pending)
        
        # [v2.4.0] Immediate Flush: For Simulation, skip price check and match all
        if has_sim:
            print(f"[v2.4.0] Flushing {len([o for o in pending if o.get('is_simulation', True)])} simulation orders for {user_id}")
            for order in pending:
                if order.get('is_simulation', True):
                    # For immediate fill, we can use the original limit price or try to find current if it helps
                    # But the requirement is "直接成立", so we'll use limit_price as the fill_price
                    # or current_price if we are already fetching it.
                    pass

        if has_sim:
            for s, t in tickers.items():
                price = None
                m_type = next((o['market'] for o in pending if o['symbol'] == s), "TW")
                
                try:
                    data = yf.download(t, period="1d", interval="1m", progress=False)
                    if not data.empty:
                        price = float(data['Close'].iloc[-1])
                        
                        # [v2.6.3] Fix: Convert USD price to TWD if the symbol is US or Crypto TWD pair
                        if m_type == "US" or (m_type == "CRYPTO" and s.lower().endswith("twd")):
                            exchange_rate = self._get_cached_exchange_rate()
                            price = price * exchange_rate
                            print(f"[TradeEngine] Converted Yahoo {s} USD price to {price:.2f} TWD (Rate: {exchange_rate:.2f})")
                except Exception as e:
                    print(f"[TradeEngine] Yahoo fetch error for {s}: {e}")
                
                if price is None and ("-USD" in t or m_type == "CRYPTO"):
                    base = t.split("-")[0]
                    try:
                        import requests
                        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={base}USDT", timeout=5)
                        if r.status_code == 200:
                            price = float(r.json()['price'])
                            
                            # [v2.6.3] Fix: Convert USD price to TWD if the symbol is a TWD pair or US market is active
                            if s.lower().endswith("twd") or m_type == "US":
                                exchange_rate = self._get_cached_exchange_rate()
                                price = price * exchange_rate
                                print(f"[TradeEngine] Converted Binance {base} USD price to {price:.2f} TWD (Rate: {exchange_rate:.2f})")
                    except Exception as e:
                        print(f"[TradeEngine] Binance fetch error for {base}: {e}")
                
                if price:
                    prices[s] = price

        api = None
        has_live = any(not o.get('is_simulation', True) for o in pending)
        if has_live:
            from api.services.shioaji_service import ShioajiService
            api = ShioajiService.get_api_client(user_id)
            if api and not hasattr(api, 'is_mock'):
                try: api.update_status()
                except: pass

        # 2. Process matches without intermediate saves
        results = [] # Store which orders matched
        for order in pending:
            symbol = order['symbol']
            limit_price = order.get('price')
            action = order['action']
            current_price = prices.get(symbol)
            is_matched = False
            is_simulation = order.get('is_simulation', True)

            if is_simulation:
                # [v2.4.0] Direct Fill: Always match
                is_matched = True
                # If current_price is available, use it (closer to 'now'), else use limit_price
                if current_price is None:
                    current_price = limit_price
            else:
                if api and not hasattr(api, 'is_mock'):
                    try:
                        trades = api.list_trades()
                        trade_id = str(order.get('trade_id'))
                        match = next((t for t in trades if str(t.order.id) == trade_id), None)
                        if match and str(match.status.status) == "Filled":
                            is_matched = True
                            if hasattr(match.status, 'filled_avg_price') and match.status.filled_avg_price:
                                current_price = float(match.status.filled_avg_price)
                            print(f"[TradeEngine] LIVE Order FILLED for {user_id}: {symbol}")
                    except Exception as e:
                        print(f"[TradeEngine] Live poll error for {user_id}: {e}")

            if is_matched:
                print(f"[TradeEngine] Order MATCHED for {user_id}: {action} {symbol} @ {current_price} (Limit: {limit_price})")
                results.append((order, current_price or limit_price))
                modified = True

        # 3. Apply all matches to the SAME logs object
        if modified:
            for order, fill_price in results:
                # IMPORTANT: Pass logs and set should_save=False
                self.execute_fill(user_id, order, fill_price, logs=logs, should_save=False)
            
            # Final atomic save
            save_user_trade_logs(user_id, logs)
            print(f"[TradeEngine] Saved {len(results)} fills for {user_id}")

    def _calculate_costs(self, market, action, total_value):
        """Calculate simulated fees and taxes based on market and action"""
        fee = 0
        tax = 0
        
        if market == "TW":
            # TW: 0.1425% fee (Buy/Sell), 0.3% tax (Sell only)
            fee = total_value * 0.001425
            if action == "Sell":
                tax = total_value * 0.003
        else:
            # US/Crypto: 0.1% flat fee
            fee = total_value * 0.001
            
        return round(fee, 2), round(tax, 2)

    def execute_fill(self, user_id, order, fill_price, logs=None, should_save=True):
        if logs is None:
            logs = get_user_trade_logs(user_id)
        
        # 1. Remove this specific order from logs (using reference or ID)
        target_id = order.get("trade_id")
        logs[:] = [L for L in logs if not (L.get("entry_type") == "PENDING" and L.get("trade_id") == target_id)]
        
        trade_id = target_id or f"AUTO-{int(time.time())}"
        symbol = order['symbol']
        name = order.get('name', symbol)
        qty = order['qty']
        action = order['action']
        market = order['market']
        is_simulation = order.get('is_simulation', True)
        total_value = fill_price * qty

        # Calculate costs for simulation
        fee, tax = 0, 0
        if is_simulation:
            fee, tax = self._calculate_costs(market, action, total_value)

        # 2. Update POSITION
        positions = [L for L in logs if L.get("entry_type") == "POSITION"]
        existing = next((p for p in positions if p['symbol'] == symbol), None)
        
        if action == 'Buy':
            # Create sub_order record for this specific buy
            sub_order = {
                "trade_id": trade_id,
                "qty": qty,
                "buy_price": fill_price,
                "fee": fee,
                "buy_order_time": order.get("order_time") or order.get("timestamp"),
                "fill_time": datetime.now().isoformat()
            }
            
            if existing:
                total_qty = existing['qty'] + qty
                # Include buy fee in cost basis
                total_cost = (existing['buy_price'] * existing['qty']) + total_value + fee
                avg_price = total_cost / total_qty
                existing['qty'] = total_qty
                existing['buy_price'] = avg_price
                existing.setdefault('sub_orders', []).append(sub_order)
            else:
                # Include buy fee in initial cost basis
                avg_price = (total_value + fee) / qty
                existing = {
                    "symbol": symbol,
                    "name": name,
                    "qty": qty,
                    "buy_price": avg_price,
                    "market": market,
                    "is_simulation": is_simulation,
                    "entry_type": "POSITION",
                    "status": "OPEN",
                    "timestamp": datetime.now().isoformat(),
                    "buy_order_time": order.get("order_time") or order.get("timestamp"),
                    "fee": fee,
                    "sub_orders": [sub_order]
                }
                logs.append(existing)

        elif action == 'Sell':
            realized_pl = 0
            pnl_percent = 0
            if existing:
                buy_cost = existing.get('buy_price', 0) * qty
                # Realized PL = (Sell Value - Fees - Tax) - Buy Cost
                realized_pl = (total_value - fee - tax) - buy_cost
                if buy_cost > 0:
                    pnl_percent = round((realized_pl / buy_cost) * 100, 2)
                    
                if existing['qty'] <= qty:
                    logs[:] = [L for L in logs if L is not existing]
                else:
                    existing['qty'] -= qty

            logs.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "name": name,
                "action": "Sell",
                "qty": qty,
                "price": fill_price,
                "buy_price": round(existing.get('buy_price', 0), 2) if existing else 0,
                "market": market,
                "status": "FILLED",
                "entry_type": "HISTORY",
                "is_simulation": is_simulation,
                "realized_pl": round(realized_pl, 2),
                "pnl_percent": pnl_percent,
                "fee": fee,
                "tax": tax,
                "timestamp": datetime.now().isoformat(),
                "order_time": order.get("timestamp"),
                "fill_time": datetime.now().isoformat()
            })

        if should_save:
            save_user_trade_logs(user_id, logs)

    def cancel_order(self, user_id, trade_id):
        """Move a pending order to history as CANCELLED"""
        from api.services.storage_service import get_user_trade_logs, save_user_trade_logs
        logs = get_user_trade_logs(user_id)
        
        # Standardize trade_id to string for reliable comparison
        target_id = str(trade_id)
        order = next((L for L in logs if str(L.get("trade_id")) == target_id and L.get("entry_type") == "PENDING"), None)
        
        if order:
            # If it's a Live Trade, attempt to cancel at broker level first
            if not order.get("is_simulation", True):
                print(f"[MatchingEngine] Attempting LIVE cancellation for {target_id} ({order.get('market')})")
                try:
                    if order.get("market") == "CRYPTO":
                        from api.services.storage_service import get_user_credentials
                        from max_api import MaxExchangeAPI
                        creds = get_user_credentials(user_id)
                        if creds.get("max_api_key"):
                            max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                            max_api.cancel_order(target_id)
                    else: # TW or US
                        from api.services.shioaji_service import ShioajiService
                        ShioajiService.cancel_order(user_id, target_id)
                except Exception as e:
                    print(f"[MatchingEngine] External cancellation error (non-blocking): {e}")

            order["entry_type"] = "HISTORY"
            order["status"] = "CANCELLED"
            order["timestamp"] = datetime.now().isoformat()
            save_user_trade_logs(user_id, logs)
            print(f"[MatchingEngine] Cancelled {target_id} for {user_id}")
            return True
        return False

    def _get_cached_exchange_rate(self):
        """Fetch USD/TWD exchange rate with a 10-minute cache to avoid rate limits."""
        now = time.time()
        if hasattr(self, '_rate_cache') and (now - self._rate_cache['ts'] < 600):
            return self._rate_cache['rate']
        
        rate = 31.0 # Default fallback
        try:
            rate_df = yf.download("TWD=X", period="1d", interval="1m", progress=False)
            if not rate_df.empty:
                rate = float(rate_df['Close'].iloc[-1])
        except Exception as e:
            print(f"[TradeEngine] Exchange rate fetch error: {e}")
        
        self._rate_cache = {'rate': rate, 'ts': now}
        return rate

engine = MatchingEngine()
