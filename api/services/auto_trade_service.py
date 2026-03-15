import time
import threading
import schedule
import asyncio
from datetime import datetime
from api.services.quant_service import run_market_scan, get_cached_pool, scan_status
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_trade_logs

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

    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def ensure_fresh_scans(self):
        """Check if cache exists for all markets, trigger if missing"""
        for m in ["TW", "US", "CRYPTO"]:
            pool = get_cached_pool(m)
            if not pool or not pool.get("results"):
                print(f"[AutoRobot] No data for {m}, triggering auto-scan...")
                self._update_status("Scanning", f"Performing initial scan for {m}...")
                asyncio.run(run_market_scan(m))
                # PROACTIVE: Try to trade immediately after first successful scan
                print(f"[AutoRobot] Initial scan for {m} finished. Attempting startup trade...")
                self.perform_daily_trade(m)
        self._update_status("Idle", "Initial scans complete. System ready.")

    def perform_daily_trade(self, market_type):
        print(f"[AutoRobot] Running daily trade for {market_type}...")
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
            
            # Fallback for price if entry_price is missing
            if not entry_price:
                entry_price = getattr(top_1, 'price', top_1.get('price', 0) if isinstance(top_1, dict) else 0)

            log_msg = f"Top candidate: {symbol} ({name}) with score {score}."
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
                is_simulation=True
            )
            if isinstance(res, dict) and "error" in res:
                self._update_status("Error", f"Order failed for {symbol}: {res['error']}")
            else:
                self._update_status("Idle", f"Successfully placed order for {symbol} @ {entry_price}")
                print(f"[AutoRobot] Simulation Trade CREATED for {symbol} at {entry_price}. Checking logs...")
                # Verify persistence immediately in logs
                from api.services.storage_service import get_user_trade_logs
                all_logs = get_user_trade_logs(self.user_id)
                if any(L.get("symbol") == symbol and L.get("entry_type") == "PENDING" for L in all_logs):
                    print(f"[AutoRobot] SUCCESS: {symbol} is now in trade_logs.")
                else:
                    print(f"[AutoRobot] WARNING: {symbol} NOT found in trade_logs after save!")
        except Exception as e:
            print(f"[AutoRobot] Trade Error for {market_type}: {e}")

    def check_exits(self):
        # TP +20% or SL -5%
        print(f"[AutoRobot] Checking exits for {self.user_id}...")
        self._update_status("ExitCheck", "Monitoring active positions for TP/SL...")
        try:
            positions = ShioajiService.get_positions(self.user_id)
            for pos in positions:
                pnl_pct = pos.get('pnl_percent', 0)
                if pnl_pct >= 20.0 or pnl_pct <= -5.0:
                    status = "Take Profit" if pnl_pct >= 20.0 else "Stop Loss"
                    print(f"[AutoRobot] Trigger {status} for {pos['symbol']} at {pnl_pct}%")

                    ShioajiService.place_order(
                        self.user_id,
                        pos['symbol'],
                        pos['qty'],
                        pos['current_price'],
                        action="Sell",
                        is_simulation=True
                    )
        except Exception as e:
            print(f"[AutoRobot] Exit Check Error: {e}")

# Singleton
robot = AutoRobot()
