import time
import random
from datetime import datetime
from api.services.storage_service import get_user_trade_logs, save_user_trade_logs, get_user_credentials
from api.services.shioaji_service import ShioajiService
from max_api import MaxExchangeAPI

class ReconciliationService:
    def sync_broker_data(self, user_id: str):
        print(f"[Recon] Starting sync for {user_id}...")
        logs = get_user_trade_logs(user_id)
        creds = get_user_credentials(user_id)
        
        initial_count = len(logs)

        # 1. Shioaji (TW/US)
        try:
            # Shioaji returns all recent trades, including filled and active
            api = ShioajiService.get_api_client(user_id)
            if api and not hasattr(api, 'is_mock'):
                api.update_status()
                real_trades = api.list_trades()
                for t in real_trades:
                    self._merge_shioaji_trade(logs, t)
        except Exception as e:
            print(f"[Recon] Shioaji Sync Error: {e}")

        # 2. MAX (Crypto)
        if creds.get("max_api_key") and creds.get("max_api_secret"):
            try:
                max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                # A. Fetch filled trades
                max_trades = max_api.get_trades()
                if isinstance(max_trades, list):
                    for mt in max_trades:
                        self._merge_max_trade(logs, mt)
                
                # B. Fetch active orders (Pending)
                max_orders = max_api.get_orders(state="wait")
                if isinstance(max_orders, list):
                    for mo in max_orders:
                        self._merge_max_order_pending(logs, mo)
            except Exception as e:
                print(f"[Recon] MAX Sync Error: {e}")

        # 3. Cleanup "Ghost" Pending Orders (Live orders only)
        # If a local live pending order is NOT found in the latest broker lists, mark it as CANCELLED
        all_real_ids = set()
        # Collect all IDs from Shioaji (real_trades contains all recent)
        try:
            if api and not hasattr(api, 'is_mock'):
                all_real_ids.update([str(t.order.id) for t in api.list_trades()])
        except: pass
        
        # Collect all IDs from MAX (both trades and pending)
        if creds.get("max_api_key"):
            try:
                # We need to consider both filled and open for MAX
                # (Simple approach: if it's not in the lists we just fetched, it's gone)
                # But to avoid race conditions, we only prune if it's "Live" and has a "FIX-" or random ID that shouldn't exist
                pass
            except: pass

        for L in logs:
            if L.get("entry_type") == "PENDING" and L.get("is_simulation") == False:
                tid = L.get("trade_id")
                # If it's a Shioaji order (TW/US) and not in real_trades anymore
                if L.get("market") in ["TW", "US"] and tid not in all_real_ids and not tid.startswith("FIX-"):
                    print(f"[Recon] Pruning ghost Shioaji order: {tid}")
                    L["status"] = "CANCELLED"
                    L["entry_type"] = "HISTORY"
                
                # Special case: Burn FIX- IDs for Sinopac that are definitely dead (today is Sunday)
                if tid.startswith("FIX-") and L.get("market") in ["TW", "US"]:
                    print(f"[Recon] Auto-cancelling failed live order: {tid}")
                    L["status"] = "CANCELLED"
                    L["entry_type"] = "HISTORY"

        final_count = len(logs)
        print(f"[Recon] Sync finished for {user_id}. Added {final_count - initial_count} records.")

        if final_count != initial_count or True: # Force save for cleanup
            save_user_trade_logs(user_id, logs)
        
        return {
            "status": "success",
            "added": final_count - initial_count,
            "total": final_count
        }

    def _merge_shioaji_trade(self, logs, trade):
        trade_id = str(trade.order.id)
        # Check if already exists in logs
        existing = next((L for L in logs if L.get("trade_id") == trade_id), None)
        
        status_str = str(trade.status.status)
        is_filled = "Filled" in status_str
        is_pending = any(s in status_str for s in ["Submitted", "PreAccepted", "PendingSubmit"])

        if existing:
            # Update status if changed (e.g. from PENDING to FILLED)
            if is_filled and existing.get("entry_type") == "PENDING":
                print(f"[Recon] Shioaji Order {trade_id} FILLED. Updating log.")
                existing["entry_type"] = "HISTORY"
                existing["status"] = "FILLED"
            return

        if not (is_filled or is_pending):
            return

        # Determine market
        symbol = trade.contract.code
        market = "TW"
        if len(symbol) > 4 and not symbol.isdigit():
            market = "US"

        print(f"[Recon] Merging missing Shioaji {status_str}: {symbol} ID:{trade_id}")
        
        new_entry = {
            "trade_id": trade_id,
            "symbol": symbol,
            "name": getattr(trade.contract, 'name', symbol),
            "action": "Buy" if "Buy" in str(trade.order.action) else "Sell",
            "qty": float(trade.order.quantity),
            "price": float(trade.order.price),
            "market": market,
            "is_simulation": False,
            "entry_type": "HISTORY" if is_filled else "PENDING",
            "status": "FILLED" if is_filled else "OPEN",
            "timestamp": str(trade.status.order_datetime) if hasattr(trade.status, 'order_datetime') else datetime.now().isoformat()
        }
        logs.append(new_entry)

    def _merge_max_trade(self, logs, mt):
        # MAX trades are executed trades
        trade_id = str(mt.get("id"))
        if any(L.get("trade_id") == trade_id for L in logs):
            return

        symbol = mt.get("market", "crypto").upper()
        if symbol.endswith("TWD"):
            symbol = symbol[:-3] + "-TWD"
        elif symbol.endswith("USDT"):
            symbol = symbol[:-4] + "-USDT"

        print(f"[Recon] Merging missing MAX trade: {symbol} ID:{trade_id}")

        new_entry = {
            "trade_id": trade_id,
            "symbol": symbol,
            "name": symbol,
            "action": "Buy" if mt.get("side") == "buy" else "Sell",
            "qty": float(mt.get("volume", 0)),
            "price": float(mt.get("price", 0)),
            "market": "CRYPTO",
            "is_simulation": False,
            "entry_type": "HISTORY",
            "status": "FILLED",
            "timestamp": mt.get("created_at", datetime.now().isoformat())
        }
        logs.append(new_entry)

    def _merge_max_order_pending(self, logs, mo):
        trade_id = str(mo.get("id"))
        if any(L.get("trade_id") == trade_id for L in logs):
            return

        symbol = mo.get("market", "crypto").upper()
        if symbol.endswith("TWD"):
            symbol = symbol[:-3] + "-TWD"
        elif symbol.endswith("USDT"):
            symbol = symbol[:-4] + "-USDT"

        print(f"[Recon] Merging missing MAX Pending order: {symbol} ID:{trade_id}")

        new_entry = {
            "trade_id": trade_id,
            "symbol": symbol,
            "name": symbol,
            "action": "Buy" if mo.get("side") == "buy" else "Sell",
            "qty": float(mo.get("volume", 0)),
            "price": float(mo.get("price", 0)),
            "market": "CRYPTO",
            "is_simulation": False,
            "entry_type": "PENDING",
            "status": "OPEN",
            "timestamp": mo.get("created_at", datetime.now().isoformat())
        }
        logs.append(new_entry)

recon_service = ReconciliationService()
