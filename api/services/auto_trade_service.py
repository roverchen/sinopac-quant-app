import time
import threading
import schedule
import asyncio
from datetime import datetime
from api.services.quant_service import run_market_scan, get_cached_pool, scan_status
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_trade_logs, get_all_users_for_notifications
from api.services.email_service import notify_trade

class AutoRobot:
    def __init__(self):
        self.user_id = "system_auto"
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.running = True
            # Setup Schedule
            # US 06:10, TW 14:10, Crypto 23:15 (Delayed slightly to ensure fresh data)
            schedule.every().day.at("06:10").do(self.perform_daily_trade, market_type="US")
            schedule.every().day.at("14:10").do(self.perform_daily_trade, market_type="TW")
            schedule.every().day.at("23:15").do(self.perform_daily_trade, market_type="CRYPTO")
            
            # Periodic checks
            schedule.every(30).minutes.do(self.check_exits)
            schedule.every(4).hours.do(self.ensure_fresh_scans)

            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            
            # Initial check at startup
            threading.Thread(target=self.ensure_fresh_scans, daemon=True).start()
            print(f"[AutoRobot] Started for {self.user_id}")
            self._update_status("Idle", "Robot started and waiting for schedule.")

    def _update_status(self, status, message):
        from api.services.storage_service import save_robot_status
        status_dict = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        save_robot_status(status_dict)

    def _notify_users(self, symbol, action, price, market, score=0):
        """Send email notifications to all subscribed users."""
        targets = get_all_users_for_notifications()
        if not targets:
            return
            
        print(f"[AutoRobot] Notifying {len(targets)} users about {action} {symbol}")
        for email, _ in targets:
            notify_trade(email, symbol, action, price, market, score)

    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def get_last_trade_time(self, market_type):
        """Retrieve the timestamp of the most recent trade for this market"""
        try:
            from api.services.storage_service import get_user_trade_logs
            logs = get_user_trade_logs(self.user_id)
            market_logs = [L for L in logs if L.get("market") == market_type]
            if not market_logs:
                return datetime.min
            
            # Sort by timestamp descending
            market_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            ts_str = market_logs[0].get("timestamp", "")
            if not ts_str: return datetime.min
            # Parse ISO format, handles both with and without microsecs
            try:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except:
                return datetime.fromisoformat(ts_str.split(".")[0])
        except Exception as e:
            print(f"[AutoRobot] Error getting last trade time: {e}")
            return datetime.min

    def ensure_fresh_scans(self):
        """Check for missing data OR missed trade windows (Robust Makeup logic)"""
        now = datetime.now()
        
        # Market schedule map
        schedule_times = {
            "US": "06:10",
            "TW": "14:10",
            "CRYPTO": "23:15"
        }

        for m, scheduled_time_str in schedule_times.items():
            # Layer 1: Data Freshness
            pool = get_cached_pool(m)
            if not pool or not pool.get("results"):
                print(f"[AutoRobot] No data for {m}, triggering auto-scan...")
                self._update_status("Scanning", f"Performing initial scan for {m}...")
                asyncio.run(run_market_scan(m))
            
            # Layer 2: Robust Makeup Logic
            # Calculate the LAST expected trade time for this market
            h, mn = map(int, scheduled_time_str.split(":"))
            target_today = now.replace(hour=h, minute=mn, second=0, microsecond=0)
            
            from datetime import timedelta
            if now >= target_today:
                last_expected = target_today
            else:
                # Target window was yesterday
                last_expected = target_today - timedelta(days=1)
            
            last_trade = self.get_last_trade_time(m)
            
            # Use a small buffer (e.g. 1 minute) to avoid double trades due to timing precision
            if last_trade < (last_expected - timedelta(minutes=1)):
                print(f"[AutoRobot] Missed window detected for {m} (Last expected: {last_expected}, Last actual: {last_trade})")
                self._update_status("Trading", f"Makeup trade for {m} (Missed window: {last_expected.strftime('%m-%d %H:%M')})")
                self.perform_daily_trade(m)
            else:
                print(f"[AutoRobot] {m} is up to date (Last trade: {last_trade}).")

        self._update_status("Idle", "Startup checks and makeup trades complete.")

    def perform_daily_trade(self, market_type):
        print(f"[AutoRobot] Running daily trade for {market_type}...")
        
        # Distributed Lock Check (v2.1.89)
        from api.services.storage_service import acquire_daily_trade_lock
        from datetime import datetime
        if not acquire_daily_trade_lock(market_type, datetime.now()):
            print(f"[AutoRobot] Skipping trade for {market_type} - Lock already held by another Cloud Run instance.")
            return
            
        self._update_status("Trading", f"Analyzing {market_type} for trade opportunities...")
        try:
            # Step 1: Ensure we have a scan (trigger one if needed)
            pool = get_cached_pool(market_type)
            if not pool or not pool.get("results"):
                print(f"[AutoRobot] Data missing for {market_type} trade, starting emergency scan...")
                asyncio.run(run_market_scan(market_type))
                pool = get_cached_pool(market_type)

            results = pool.get("results", [])
            if not results:
                print(f"[AutoRobot] No results found for {market_type} after emergency scan.")
                return

            # Explicitly sort by score just in case
            try:
                # Handle both object (Pydantic) and dict types
                results = sorted(results, key=lambda x: getattr(x, 'score', 0) if not isinstance(x, dict) else x.get('score', 0), reverse=True)
            except:
                pass

            # Pick Top 1
            top_1 = results[0]
            # Handle potential dictionary or object access
            symbol = getattr(top_1, 'symbol', top_1.get('symbol', '') if isinstance(top_1, dict) else '')
            name = getattr(top_1, 'name', top_1.get('name', '') if isinstance(top_1, dict) else '')
            entry_price = getattr(top_1, 'entry_price', top_1.get('entry_price', 0) if isinstance(top_1, dict) else 0)
            score = getattr(top_1, 'score', top_1.get('score', 0) if isinstance(top_1, dict) else 0)
            
            pullback_score = getattr(top_1, 'pullback_score', top_1.get('pullback_score', 0) if isinstance(top_1, dict) else 0)
            value_score = getattr(top_1, 'value_score', top_1.get('value_score', 0) if isinstance(top_1, dict) else 0)

            log_msg = f"Top candidate: {symbol} ({name}) with score {score} (V:{value_score}/P:{pullback_score})."
            print(f"[AutoRobot] {log_msg}")
            self._update_status("Trading", log_msg)

            # Execution logic (TW: 1000 shares, US: 10, Crypto: 0.1)
            qty = 1000 if market_type == "TW" else (10 if market_type == "US" else 0.1)

            res = ShioajiService.place_order(
                self.user_id,
                symbol,
                qty,
                entry_price,
                action="Buy",
                is_simulation=True,
                name=name
            )
            if isinstance(res, dict) and "error" in res:
                self._update_status("Error", f"Order failed for {symbol}: {res['error']}")
            else:
                self._update_status("Idle", f"Successfully placed order for {symbol} @ {entry_price}")
                print(f"[AutoRobot] Simulation Trade CREATED for {symbol} at {entry_price}. Checking logs...")
                # Notify users (Email)
                self._notify_users(symbol, "Buy", entry_price, market_type, score)
                
                # MIRROR TRADING: Follow-up for other users
                self._execute_mirror_buys(symbol, entry_price, market_type, name, value_score, pullback_score)

                # Verify persistence immediately in logs
                from api.services.storage_service import get_user_trade_logs
                all_logs = get_user_trade_logs(self.user_id)
                if any(L.get("symbol") == symbol and L.get("entry_type") == "PENDING" for L in all_logs):
                    print(f"[AutoRobot] SUCCESS: {symbol} is now in trade_logs.")
                else:
                    print(f"[AutoRobot] WARNING: {symbol} NOT found in trade_logs after save!")
        except Exception as e:
            print(f"[AutoRobot] Trade Error for {market_type}: {e}")

    def _execute_mirror_buys(self, symbol, entry_price, market_type, name, value_score=0, pullback_score=0):
        """Execute mirror trades for all authorized followers based on their weights and balances."""
        from api.services.storage_service import get_all_users_with_auto_trade, get_user_settings, get_user_credentials
        follower_ids = get_all_users_with_auto_trade()
        
        for uid in follower_ids:
            if uid == self.user_id: continue # Already traded
            
            settings = get_user_settings(uid)
            # SAFETY CHECK: Must be confirmed
            if not settings.get("mirror_trading_confirmed", False):
                print(f"[AutoRobot] Mirror trading NOT confirmed for {uid}. Skipping.")
                continue
            
            creds = get_user_credentials(uid)
            is_simulation = creds.get("simulation_mode", True)
            
            # BALANCE CHECK & QTY CALCULATION
            try:
                # Use Shioaji balance for now (extensible to MAX)
                balance = ShioajiService.get_balance(uid)
                if not isinstance(balance, (int, float)) or balance <= 0:
                    print(f"[AutoRobot] Invalid balance for {uid}: {balance}. Skipping.")
                    continue
                
                # [v2.1.86] Budget-Based Allocation
                # total_allocation_pct is the max % of balance (e.g., 10%)
                # strategy_ratio (0.0 to 1.0) splits that max %
                total_pct = settings.get("total_allocation_pct", 10.0) / 100.0
                ratio = settings.get("strategy_ratio", 0.5)

                if pullback_score * 0.5 >= value_score * 0.5:
                    # Scaling by ratio: if ratio is 1.0, use full total_pct
                    weight = total_pct * ratio
                else:
                    # Scaling by (1-ratio): if ratio is 0.0, use full total_pct
                    weight = total_pct * (1 - ratio)

                order_value = balance * weight
                
                # [v2.1.85] Absolute Trade Limit
                max_limit = settings.get("max_order_limit", 50000.0)
                if order_value > max_limit:
                    print(f"[AutoRobot] Order value {order_value} exceeds limit {max_limit} for {uid}. Capping.")
                    order_value = max_limit

                if order_value < 100: # Threshold for too small order
                    print(f"[AutoRobot] Balance too low for {uid} to mirror trade {symbol}")
                    continue
                
                # Calc Qty (TW: round to nearest 1000/1, US: floor, Crypto: floor)
                if market_type == "TW":
                    # Simple estimation: price * 1.005 to cover fees
                    qty = int(order_value / (entry_price * 1.005)) 
                    qty = (qty // 1000) * 1000 if qty >= 1000 else qty
                elif market_type == "US":
                    qty = int(order_value / entry_price)
                else:
                    qty = round(order_value / entry_price, 4)

                if qty <= 0: continue

                print(f"[AutoRobot] Mirror trading for {uid}: {symbol} x {qty} (@{entry_price})")
                ShioajiService.place_order(
                    uid, symbol, qty, entry_price, action="Buy",
                    is_simulation=is_simulation, name=name
                )
            except Exception as e:
                print(f"[AutoRobot] Failed to mirror trade for {uid}: {e}")

    def check_exits(self):
        """Check exits for system_auto AND all authorized followers using their custom TP/SL."""
        from api.services.storage_service import get_all_users_with_auto_trade, get_user_settings
        
        print(f"[AutoRobot] Running multi-user exit checks...")
        
        # 1. System Auto Exits (Fixed 20% / -5%)
        self._check_user_exits(self.user_id, 20.0, -5.0)
        
        # 2. Follower Exits (Customized)
        followers = get_all_users_with_auto_trade()
        for uid in followers:
            if uid == self.user_id: continue
            settings = get_user_settings(uid)
            if not settings.get("mirror_trading_confirmed", False): continue
            
            tp = settings.get("tp_pct", 20.0)
            sl = settings.get("sl_pct", -5.0)
            self._check_user_exits(uid, tp, sl)

    def _check_user_exits(self, user_id, tp_pct, sl_pct):
        """Monitor active positions for a specific user and trigger TP/SL."""
        try:
            from api.services.storage_service import get_user_credentials
            from api.services.email_service import notify_trade
            
            creds = get_user_credentials(user_id)
            is_simulation = creds.get("simulation_mode", True)
            
            positions = ShioajiService.get_positions(user_id)
            for pos in positions:
                pnl_pct = pos.get('pnl_percent', 0)
                if pnl_pct >= tp_pct or pnl_pct <= sl_pct:
                    status = "Take Profit" if pnl_pct >= tp_pct else "Stop Loss"
                    print(f"[AutoRobot] Trigger {status} for {user_id}: {pos['symbol']} @ {pnl_pct}%")

                    ShioajiService.place_order(
                        user_id,
                        pos['symbol'],
                        pos['qty'],
                        pos['current_price'],
                        action="Sell",
                        is_simulation=is_simulation
                    )
                    # Notify user (Email)
                    notify_trade(user_id, pos['symbol'], "Sell", pos['current_price'], pos.get('market', 'UNKNOWN'))
        except Exception as e:
            print(f"[AutoRobot] Exit Check Error for {user_id}: {e}")

# Singleton
robot = AutoRobot()
