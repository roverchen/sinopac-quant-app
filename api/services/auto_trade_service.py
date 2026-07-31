import asyncio
import schedule
import threading
import time
from datetime import datetime, timedelta

from api.services.email_service import notify_trade
from api.services.quant_service import get_cached_pool, run_market_scan
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_all_users_for_notifications, get_user_trade_logs
from api.services.strategy_accounts import (
    get_strategy_account,
    list_strategy_accounts,
    supports_market,
)


class AutoRobot:
    def __init__(self):
        self.primary_user_id = "system_auto"
        self.thread = None
        self.running = False
        self._is_scanning = False  # [v2.7.6] Flag to prevent redundant concurrent scans
        self.daily_wakeup_time = "23:20"

    def start(self):
        if not self.running:
            self.running = True
            # Run one consolidated daily wakeup. The wakeup flow will makeup any
            # missed US/TW/Crypto trade windows through ensure_fresh_scans().
            schedule.every().day.at(self.daily_wakeup_time).do(
                lambda: threading.Thread(target=self.ensure_fresh_scans, daemon=True).start()
            )

            # Periodic checks (v2.8.0: Every 1 minute to catch fast crashes / SL slippage)
            schedule.every(1).minutes.do(lambda: threading.Thread(target=self.check_exits, daemon=True).start())

            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()

            # [v2.7.7] Delayed startup scan to avoid blocking Cloud Run health checks
            def delayed_check():
                time.sleep(30)
                self.ensure_fresh_scans()
            
            threading.Thread(target=delayed_check, daemon=True).start()
            print("[AutoRobot] Started multi-strategy simulation engine.")
            self._update_status("Idle", f"Robot started and waiting for daily wakeup at {self.daily_wakeup_time}.")

    def _run_coroutine(self, coro):
        """Safely run an async coroutine from either sync or async context."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                # We are in an async context, but we need this to finish.
                # In FastAPI, we can't block the loop. 
                # This helper is now primarily to detect the loop and warn.
                return loop.create_task(coro)
        except RuntimeError:
            return asyncio.run(coro)
        
    def _check_and_reset_stuck_robot(self):
        """Self-healing: If robot is stuck in a non-Idle state for >30 mins, reset it."""
        from api.services.storage_service import get_robot_status
        status_data = get_robot_status()
        if not status_data or status_data.get("status") == "Idle":
            return

        last_updated_str = status_data.get("last_updated")
        if not last_updated_str:
            return

        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00")).replace(tzinfo=None)
            diff = (datetime.now() - last_updated).total_seconds()
            if diff > 1800: # 30 minutes
                print(f"[AutoRobot] Self-Healing: Detected stuck state '{status_data.get('status')}' (Updated {diff/60:.1f} mins ago). Resetting to Idle.")
                self._update_status("Idle", f"Self-healed from stuck state: {status_data.get('status')}")
        except Exception as e:
            print(f"[AutoRobot] Self-Healing Check Error: {e}")

    def _update_status(self, status, message):
        from api.services.storage_service import save_robot_status

        status_dict = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "heartbeat": datetime.now().isoformat()
        }
        save_robot_status(status_dict)

    def _notify_users(self, symbol, action, price, market, score=0, pnl_pct=None, pnl_amount=None):
        """Send email notifications to all subscribed users."""
        targets = get_all_users_for_notifications()
        if not targets:
            return

        print(f"[AutoRobot] Notifying {len(targets)} users about {action} {symbol}")
        for email, _ in targets:
            notify_trade(email, symbol, action, price, market, score, pnl_pct=pnl_pct, pnl_amount=pnl_amount)

    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def get_last_trade_time(self, user_id, market_type):
        """Retrieve the timestamp of the most recent trade for this user and market."""
        try:
            logs = get_user_trade_logs(user_id)
            market_logs = [L for L in logs if L.get("market") == market_type]
            if not market_logs:
                return datetime.min

            market_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            ts_str = market_logs[0].get("timestamp", "")
            if not ts_str:
                return datetime.min
            try:
                return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except Exception:
                return datetime.fromisoformat(ts_str.split(".")[0])
        except Exception as e:
            print(f"[AutoRobot] Error getting last trade time for {user_id}: {e}")
            return datetime.min

    def _parse_percent(self, raw_value, default=0.0):
        try:
            if raw_value is None:
                return default
            if isinstance(raw_value, (int, float)):
                return float(raw_value)
            return float(str(raw_value).replace("%", "").strip())
        except Exception:
            return default

    def _pick_rover_candidate(self, results):
        if not results:
            return None
        return results[0]

    def _pick_eric_candidate(self, results):
        """
        TW-only swing strategy inspired by strategy-eric.md:
        prefer strong bullish trend structure, healthy pullback, and non-exhausted levels.
        """
        ranked = []
        for result in results:
            market = getattr(result, "market", result.get("market", "TW") if isinstance(result, dict) else "TW")
            if market != "TW":
                continue

            pullback_score = float(getattr(result, "pullback_score", result.get("pullback_score", 0) if isinstance(result, dict) else 0) or 0)
            value_score = float(getattr(result, "value_score", result.get("value_score", 0) if isinstance(result, dict) else 0) or 0)
            rs_score = float(getattr(result, "rs_score", result.get("rs_score", 0) if isinstance(result, dict) else 0) or 0)
            opening_strength = float(getattr(result, "opening_strength", result.get("opening_strength", 0) if isinstance(result, dict) else 0) or 0)
            macd_status = getattr(result, "macd_status", result.get("macd_status", "") if isinstance(result, dict) else "") or ""
            level = self._parse_percent(getattr(result, "level", result.get("level", 0) if isinstance(result, dict) else 0))
            ma20_diff = self._parse_percent(getattr(result, "ma20_diff", result.get("ma20_diff", 0) if isinstance(result, dict) else 0))

            if "Bullish" not in macd_status:
                continue
            if level < 15 or level > 82:
                continue
            if ma20_diff < -3.5 or ma20_diff > 8.0:
                continue

            near_ma20_bonus = max(0.0, 8.0 - abs(ma20_diff))
            level_bonus = max(0.0, 18.0 - abs(level - 45.0)) * 0.35
            composite = (
                pullback_score * 0.45
                + rs_score * 0.30
                + value_score * 0.10
                + opening_strength * 8.0
                + near_ma20_bonus
                + level_bonus
            )
            ranked.append((composite, result))

        if ranked:
            ranked.sort(key=lambda item: item[0], reverse=True)
            return ranked[0][1]

        # Fallback to best TW result if no candidate meets the stricter filters.
        tw_results = [
            r for r in results
            if getattr(r, "market", r.get("market", "TW") if isinstance(r, dict) else "TW") == "TW"
        ]
        return tw_results[0] if tw_results else None

    def _select_trade_candidate(self, strategy_key, market_type, results):
        if strategy_key == "eric":
            return self._pick_eric_candidate(results)
        return self._pick_rover_candidate(results)

    def ensure_fresh_scans(self):
        """Check for missing data OR missed trade windows (robust makeup logic)."""
        # [v2.7.6] Guard against concurrent scans
        if self._is_scanning:
            print("[AutoRobot] Scan already in progress, skipping ensure_fresh_scans.")
            return
        
        self._is_scanning = True
        try:
            # [v2.7.5] Perform self-healing check before starting
            self._check_and_reset_stuck_robot()
        
            now = datetime.now()
            schedule_times = {
                "US": "06:10",
                "TW": "14:10",
                "CRYPTO": "23:15",
            }

            for market_type, scheduled_time_str in schedule_times.items():
                pool = get_cached_pool(market_type)
                is_missing = not pool or not pool.get("results")
                is_stale = False

                if pool and pool.get("timestamp"):
                    try:
                        pool_ts = datetime.fromisoformat(pool["timestamp"].replace("Z", "+00:00"))
                        if (now - pool_ts.replace(tzinfo=None)).total_seconds() > 86400:
                            is_stale = True
                    except Exception:
                        is_stale = True

                if is_missing or is_stale:
                    reason = "Missing data" if is_missing else "Stale data (>24h)"
                    print(f"[AutoRobot] {reason} for {market_type}, triggering auto-scan...")
                    self._update_status("Scanning", f"Performing {reason} scan for {market_type}...")
                    
                    # [v2.7.5] Use safe runner to avoid "asyncio.run() from running loop" errors
                    task = self._run_coroutine(run_market_scan(market_type))
                    # If it's a task (async context), we should wait for it if possible, 
                    # but here we are in a sync function often called via wakeup.
                    if isinstance(task, asyncio.Task):
                        # This is tricky in a sync method. For now, we'll block if we can 
                        # but ensure_fresh_scans is often called in a thread.
                        pass 

                h, mn = map(int, scheduled_time_str.split(":"))
                target_today = now.replace(hour=h, minute=mn, second=0, microsecond=0)
                last_expected = target_today if now >= target_today else target_today - timedelta(days=1)

                for strategy in list_strategy_accounts():
                    user_id = strategy["user_id"]
                    if not supports_market(user_id, market_type):
                        continue

                    last_trade = self.get_last_trade_time(user_id, market_type)
                    if last_trade < (last_expected - timedelta(minutes=1)):
                        print(
                            f"[AutoRobot] Missed window detected for {user_id}/{market_type} "
                            f"(Last expected: {last_expected}, Last actual: {last_trade})"
                        )
                        self._update_status(
                            "Trading",
                            f"{strategy['short_label']} makeup trade for {market_type} "
                            f"({last_expected.strftime('%m-%d %H:%M')})",
                        )
                        self.perform_daily_trade(market_type, strategy_user_id=user_id)
                    else:
                        print(f"[AutoRobot] {user_id}/{market_type} is up to date (Last trade: {last_trade}).")

            self._update_status("Idle", "Startup checks and makeup trades complete.")
        except Exception as e:
            print(f"[AutoRobot] ensure_fresh_scans error: {e}")
            self._update_status("Error", f"Error during fresh scans: {e}")
        finally:
            self._is_scanning = False

    def perform_daily_trade(self, market_type, strategy_user_id=None):
        strategy_user_id = strategy_user_id or self.primary_user_id
        strategy = get_strategy_account(strategy_user_id)
        if not strategy or not supports_market(strategy_user_id, market_type):
            print(f"[AutoRobot] Strategy {strategy_user_id} does not support market {market_type}.")
            return

        print(f"[AutoRobot] Running {strategy['short_label']} daily trade for {market_type}...")

        from api.services.storage_service import acquire_daily_trade_lock, get_user_settings
        if not acquire_daily_trade_lock(market_type, datetime.now(), user_id=strategy_user_id):
            print(
                f"[AutoRobot] Skipping trade for {strategy_user_id}/{market_type} - "
                "lock already held by another Cloud Run instance."
            )
            return

        self._update_status("Trading", f"Analyzing {market_type} for {strategy['short_label']} opportunities...")
        try:
            pool = get_cached_pool(market_type)
            if not pool or not pool.get("results"):
                print(f"[AutoRobot] Data missing for {market_type} trade, starting emergency scan...")
                self._run_coroutine(run_market_scan(market_type))
                pool = get_cached_pool(market_type)

            results = pool.get("results", []) if pool else []
            if not results:
                print(f"[AutoRobot] No results found for {market_type} after emergency scan.")
                return

            try:
                results = sorted(
                    results,
                    key=lambda x: getattr(x, "score", 0) if not isinstance(x, dict) else x.get("score", 0),
                    reverse=True,
                )
            except Exception:
                pass

            candidate = self._select_trade_candidate(strategy["strategy_key"], market_type, results)
            if not candidate:
                print(f"[AutoRobot] No qualified candidate for {strategy_user_id}/{market_type}.")
                return

            symbol = getattr(candidate, "symbol", candidate.get("symbol", "") if isinstance(candidate, dict) else "")
            name = getattr(candidate, "name", candidate.get("name", "") if isinstance(candidate, dict) else "")
            entry_price = getattr(candidate, "entry_price", candidate.get("entry_price", 0) if isinstance(candidate, dict) else 0)
            score = getattr(candidate, "score", candidate.get("score", 0) if isinstance(candidate, dict) else 0)
            pullback_score = getattr(candidate, "pullback_score", candidate.get("pullback_score", 0) if isinstance(candidate, dict) else 0)
            value_score = getattr(candidate, "value_score", candidate.get("value_score", 0) if isinstance(candidate, dict) else 0)

            log_msg = (
                f"{strategy['short_label']} top candidate: {symbol} ({name}) "
                f"with score {score} (V:{value_score}/P:{pullback_score})."
            )
            print(f"[AutoRobot] {log_msg}")

            current_price = ShioajiService.get_current_price(symbol, market_type)
            if current_price:
                diff = abs(current_price - entry_price) / entry_price
                if diff > 0.03:
                    msg = f"Skipping {symbol}: Price Divergence too high ({diff * 100:.1f}% > 3%)"
                    print(f"[AutoRobot] {msg}")
                    self._update_status("Idle", msg)
                    return
                entry_price = current_price

            self._update_status("Trading", log_msg)

            settings = get_user_settings(strategy_user_id)
            sip_amount = settings.get("sip_amount_twd", 10000.0)
            # [v2.8.0] Apply per-market position sizing (e.g. CRYPTO = 0.5x)
            from api.services.strategy_accounts import get_market_params
            sip_amount = sip_amount * get_market_params(market_type).get("sip_multiplier", 1.0)

            price_twd = entry_price

            qty = sip_amount / price_twd
            if market_type == "TW":
                qty = int(qty)
            elif market_type == "US":
                qty = int(qty)
            else:
                qty = round(qty, 4)

            if qty <= 0:
                msg = f"Skipping {symbol}: Calculated quantity {qty} is too low for amount {sip_amount}"
                print(f"[AutoRobot] {msg}")
                self._update_status("Idle", msg)
                return

            # [v2.7.9] Convert order price to native currency if it is USD-denominated
            from api.services.shioaji_service import is_usd_denominated
            order_price = entry_price
            if is_usd_denominated(symbol, market_type):
                from api.services.trade_engine import engine
                rate = engine._get_cached_exchange_rate()
                order_price = entry_price / rate

            res = ShioajiService.place_order(
                strategy_user_id,
                symbol,
                qty,
                order_price,
                action="Buy",
                is_simulation=True,
                name=name,
            )
            if isinstance(res, dict) and "error" in res:
                self._update_status("Error", f"Order failed for {symbol}: {res['error']}")
                return

            self._update_status(
                "Idle",
                f"{strategy['short_label']} placed order for {symbol} ({qty} units) @ {entry_price}",
            )
            print(
                f"[AutoRobot] {strategy['short_label']} simulation trade CREATED for "
                f"{symbol} at {entry_price} (Qty: {qty})."
            )

            if strategy.get("send_notifications"):
                self._notify_users(symbol, "Buy", entry_price, market_type, score)

            if strategy.get("mirror_followers"):
                self._execute_mirror_buys(symbol, entry_price, market_type, name, value_score, pullback_score)

        except Exception as e:
            print(f"[AutoRobot] Trade Error for {strategy_user_id}/{market_type}: {e}")

    def _execute_mirror_buys(self, symbol, entry_price, market_type, name, value_score=0, pullback_score=0):
        """Execute mirror trades for all authorized followers based on their weights and balances."""
        from api.services.storage_service import get_all_users_with_auto_trade, get_user_credentials, get_user_settings

        follower_ids = get_all_users_with_auto_trade()

        for uid in follower_ids:
            if uid == self.primary_user_id:
                continue

            settings = get_user_settings(uid)
            if not settings.get("mirror_trading_confirmed", False):
                print(f"[AutoRobot] Mirror trading NOT confirmed for {uid}. Skipping.")
                continue

            creds = get_user_credentials(uid)
            is_simulation = creds.get("simulation_mode", True)

            try:
                balance = ShioajiService.get_balance(uid)
                if not isinstance(balance, (int, float)) or balance <= 0:
                    print(f"[AutoRobot] Invalid balance for {uid}: {balance}. Skipping.")
                    continue

                order_value = settings.get("sip_amount_twd", 10000.0)
                # [v2.8.0] Apply per-market position sizing to mirrored followers
                from api.services.strategy_accounts import get_market_params
                order_value = order_value * get_market_params(market_type).get("sip_multiplier", 1.0)
                max_limit = settings.get("max_order_limit", 50000.0)
                if order_value > max_limit:
                    print(f"[AutoRobot] SIP value {order_value} exceeds limit {max_limit} for {uid}. Capping.")
                    order_value = max_limit

                price_twd = entry_price

                qty = order_value / price_twd
                if market_type == "TW":
                    qty = int(qty)
                elif market_type == "US":
                    qty = int(qty)
                else:
                    qty = round(qty, 4)

                if qty <= 0:
                    continue

                # [v2.7.9] Convert order price to native currency if it is USD-denominated
                from api.services.shioaji_service import is_usd_denominated
                order_price = entry_price
                if is_usd_denominated(symbol, market_type):
                    from api.services.trade_engine import engine
                    rate = engine._get_cached_exchange_rate()
                    order_price = entry_price / rate

                print(f"[AutoRobot] Mirror trading for {uid}: {symbol} x {qty} (@{order_price} native)")
                ShioajiService.place_order(
                    uid,
                    symbol,
                    qty,
                    order_price,
                    action="Buy",
                    is_simulation=is_simulation,
                    name=name,
                )
            except Exception as e:
                print(f"[AutoRobot] Failed to mirror trade for {uid}: {e}")

    def check_exits(self):
        """Check exits for system strategy accounts and all authorized followers."""
        from api.services.storage_service import get_all_users_with_auto_trade, get_user_settings

        print("[AutoRobot] Running multi-user exit checks...")

        for strategy in list_strategy_accounts():
            # [v2.8.0] Strategy accounts use per-market TP/SL (None => resolve by position market)
            self._check_user_exits(strategy["user_id"])

        followers = get_all_users_with_auto_trade()
        for uid in followers:
            settings = get_user_settings(uid)
            if not settings.get("mirror_trading_confirmed", False):
                continue

            tp = settings.get("tp_pct", 20.0)
            sl = settings.get("sl_pct", -5.0)
            self._check_user_exits(uid, tp, sl)

    def _execute_exit(self, user_id, pos, status):
        """Place a sell order for a position hitting TP/SL/hard-stop and notify users."""
        try:
            from api.services.storage_service import get_user_credentials, get_user_settings

            creds = get_user_credentials(user_id)
            is_simulation = creds.get("simulation_mode", True)

            # [v2.7.9] Convert exit current_price to native currency if USD-denominated
            from api.services.shioaji_service import is_usd_denominated
            pos_market = pos.get("market", "UNKNOWN")
            order_price = pos["current_price"]
            if is_usd_denominated(pos["symbol"], pos_market):
                from api.services.trade_engine import engine
                rate = engine._get_cached_exchange_rate()
                order_price = pos["current_price"] / rate

            ShioajiService.place_order(
                user_id,
                pos["symbol"],
                pos["qty"],
                order_price,
                action="Sell",
                is_simulation=is_simulation,
            )

            # [v2.7.2] Pass PnL metrics to notification
            strategy_ids = [s["user_id"] for s in list_strategy_accounts()]
            if user_id in strategy_ids:
                self._notify_users(
                    pos["symbol"], "Sell",
                    pos["current_price"],
                    pos.get("market", "UNKNOWN"),
                    pnl_pct=pos.get("pnl_percent"),
                    pnl_amount=pos.get("pnl")
                )
            else:
                settings = get_user_settings(user_id)
                user_email = settings.get("email") or user_id
                notify_trade(
                    user_email,
                    pos["symbol"], "Sell",
                    pos["current_price"],
                    pos.get("market", "UNKNOWN"),
                    pnl_pct=pos.get("pnl_percent"),
                    pnl_amount=pos.get("pnl")
                )
        except Exception as e:
            print(f"[AutoRobot] Exit Order Error for {user_id}/{pos.get('symbol')}: {e}")

    def _check_user_exits(self, user_id, tp_pct=None, sl_pct=None):
        """Monitor active positions for a specific user and trigger TP/SL.

        If tp_pct/sl_pct are None, resolve per-market params from
        strategy_accounts.MARKET_PARAMS based on each position's market.
        """
        try:
            positions = ShioajiService.get_positions(user_id)
            for pos in positions:
                pnl_pct = pos.get("pnl_percent", 0)

                if tp_pct is None or sl_pct is None:
                    from api.services.strategy_accounts import get_market_params
                    market_params = get_market_params(pos.get("market", "UNKNOWN"))
                    eff_tp = market_params["tp_pct"]
                    eff_sl = market_params["sl_pct"]
                else:
                    eff_tp = tp_pct
                    eff_sl = sl_pct

                # [v2.7.2] Data Sanity Check: TW/US cannot plausibly drop >90% in a day.
                # Only skip NON-crypto (likely a currency-mismatch data bug). CRYPTO can
                # genuinely crash >90% (e.g. alicetwd -96.8%), so let those exit normally.
                if pnl_pct <= -90:
                    pos_market = pos.get("market", "UNKNOWN")
                    if pos_market != "CRYPTO":
                        print(f"[AutoRobot] WARNING: Abnormal ROI {pnl_pct}% for {pos['symbol']}. Skipping exit to prevent data-bug sell.")
                        continue

                # [v2.8.0] Hard stop: never hold a position past -50% (real crash).
                # This catches catastrophic drops even if intermediate checks were missed.
                if pnl_pct <= -50.0:
                    print(f"[AutoRobot] HARD STOP for {user_id}: {pos['symbol']} @ {pnl_pct}%")
                    self._execute_exit(user_id, pos, "Stop Loss")
                    continue

                if pnl_pct >= eff_tp or pnl_pct <= eff_sl:
                    status = "Take Profit" if pnl_pct >= eff_tp else "Stop Loss"
                    print(f"[AutoRobot] Trigger {status} for {user_id}: {pos['symbol']} @ {pnl_pct}%")
                    self._execute_exit(user_id, pos, status)
        except Exception as e:
            print(f"[AutoRobot] Exit Check Error for {user_id}: {e}")


robot = AutoRobot()
