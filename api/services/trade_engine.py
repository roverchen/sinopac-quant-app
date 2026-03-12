import time
import threading
from datetime import datetime
import yfinance as yf
from api.services.storage_service import (
    get_user_pending_orders,
    save_user_pending_orders,
    get_user_mock_positions,
    save_user_mock_positions,
    get_user_trade_history,
    save_user_trade_history
)
from api.services.quant_service import get_yahoo_ticker

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
        # Dynamically find all users who have pending orders to check
        from api.services.storage_service import get_all_users_with_pending
        active_users = get_all_users_with_pending()
        
        # Ensure system_auto is always checked if not in list
        if 'system_auto' not in active_users:
            active_users.append('system_auto')
            
        for user_id in active_users:
            self._check_pending_orders(user_id)

    def _check_pending_orders(self, user_id):
        pending = get_user_pending_orders(user_id)
        if not pending:
            return

        filled_indices = []
        new_pending = []

        # Batch symbols to fetch latest prices
        symbols = list(set([o['symbol'] for o in pending]))
        tickers = {s: get_yahoo_ticker(s, next(o['market'] for o in pending if o['symbol'] == s)) for s in symbols}

        # Fetch current prices for simulation orders
        prices = {}
        has_sim = any(o.get('is_simulation', True) for o in pending)
        if has_sim:
            for s, t in tickers.items():
                try:
                    data = yf.download(t, period="1d", interval="1m", progress=False)
                    if not data.empty:
                        prices[s] = data['Close'].iloc[-1]
                except:
                    continue

        # Get API client for live order status checking
        api = None
        has_live = any(not o.get('is_simulation', True) for o in pending)
        if has_live:
            from api.services.shioaji_service import ShioajiService
            api = ShioajiService.get_api_client(user_id)
            if api and not hasattr(api, 'is_mock'):
                try:
                    api.update_status()
                except:
                    pass

        for order in pending:
            symbol = order['symbol']
            limit_price = order.get('price')
            action = order['action'] # 'Buy' or 'Sell'
            current_price = prices.get(symbol)

            if current_price is None:
                new_pending.append(order)
                continue

            is_matched = False
            is_simulation = order.get('is_simulation', True)

            if is_simulation:
                # Simulation Logic: Match based on price
                if current_price is not None:
                    if action == 'Buy' and current_price <= limit_price:
                        is_matched = True
                    elif action == 'Sell' and current_price >= limit_price:
                        is_matched = True
            else:
                # Live Logic: Poll broker API status
                if api and not hasattr(api, 'is_mock'):
                    try:
                        trades = api.list_trades()
                        trade_id = str(order.get('trade_id'))
                        match = next((t for t in trades if str(t.order.id) == trade_id), None)
                        if match and str(match.status.status) == "Filled":
                            is_matched = True
                            # For live, we use the actual fill price from the API if possible
                            if hasattr(match.status, 'filled_avg_price') and match.status.filled_avg_price:
                                current_price = float(match.status.filled_avg_price)
                            print(f"[TradeEngine] LIVE Order FILLED for {user_id}: {symbol}")
                    except Exception as e:
                        print(f"[TradeEngine] Live poll error for {user_id}: {e}")

            if is_matched:
                print(f"[TradeEngine] Order MATCHED for {user_id}: {action} {symbol} @ {current_price} (Limit: {limit_price})")
                self._execute_fill(user_id, order, current_price or limit_price)
            else:
                new_pending.append(order)

        if len(new_pending) != len(pending):
            save_user_pending_orders(user_id, new_pending)

    def _execute_fill(self, user_id, order, fill_price):
        """Execute the actual movement of assets once matched."""
        positions = get_user_mock_positions(user_id)
        history = get_user_trade_history(user_id)

        trade_id = order.get('trade_id', f"AUTO-{int(time.time())}")
        symbol = order['symbol']
        qty = order['qty']
        action = order['action']
        market = order['market']

        is_simulation = order.get('is_simulation', True)

        if action == 'Buy':
            # Add to positions
            existing = next((p for p in positions if p['symbol'] == symbol), None)
            if existing:
                # Average down/up
                total_qty = existing['qty'] + qty
                avg_price = (existing['buy_price'] * existing['qty'] + fill_price * qty) / total_qty
                existing['qty'] = total_qty
                existing['buy_price'] = avg_price
            else:
                positions.append({
                    "symbol": symbol,
                    "qty": qty,
                    "buy_price": fill_price,
                    "market": market,
                    "is_simulation": is_simulation
                })

            # Record history
            history.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "action": "Buy",
                "qty": qty,
                "price": fill_price,
                "market": market,
                "status": "Filled",
                "is_simulation": is_simulation,
                "timestamp": datetime.now().isoformat()
            })

        elif action == 'Sell':
            # Remove/Decrease position
            existing = next((p for p in positions if p['symbol'] == symbol), None)
            realized_pl = 0
            if existing:
                realized_pl = (fill_price - existing['buy_price']) * min(qty, existing['qty'])
                if existing['qty'] <= qty:
                    positions = [p for p in positions if p['symbol'] != symbol]
                else:
                    existing['qty'] -= qty

            # Record history
            history.append({
                "trade_id": trade_id,
                "symbol": symbol,
                "action": "Sell",
                "qty": qty,
                "price": fill_price,
                "market": market,
                "status": "Filled",
                "is_simulation": is_simulation,
                "realized_pl": realized_pl,
                "timestamp": datetime.now().isoformat()
            })

        save_user_mock_positions(user_id, positions)
        save_user_trade_history(user_id, history)

# Singleton instance
engine = MatchingEngine()
