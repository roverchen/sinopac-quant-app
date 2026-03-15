import time
import json
from datetime import datetime
from api.services.storage_service import get_user_trade_logs, save_user_trade_logs, get_user_credentials
from api.services.shioaji_service import ShioajiService
from api.services.quant_service import get_symbol_name
from max_api import MaxExchangeAPI

class ReconciliationService:
    @staticmethod
    def sync_broker_data(user_id: str):
        """
        Fetch real-time data from brokers (MAX, Shioaji) and sync into local trade_logs.
        """
        print(f"[Sync] Starting broker synchronization for {user_id}...")
        logs = get_user_trade_logs(user_id)
        
        # Split logs into simulation and real trades
        # We only reconcile real trades
        sim_logs = [L for L in logs if L.get("is_simulation", True)]
        real_logs = [L for L in logs if not L.get("is_simulation", True)]
        
        # 1. Fetch from MAX (Crypto)
        real_logs = ReconciliationService._sync_max_data(user_id, real_logs)
        
        # 2. Fetch from Shioaji (TW/US)
        real_logs = ReconciliationService._sync_shioaji_data(user_id, real_logs)
        
        # 3. Merge back and save
        final_logs = sim_logs + real_logs
        save_user_trade_logs(user_id, final_logs)
        print(f"[Sync] Finished broker synchronization for {user_id}.")
        return {"status": "success", "count": len(real_logs)}

    @staticmethod
    def _normalize_crypto_symbol(market_id: str):
        """Convert btcusdt to BTC-USD and polusdt to MATIC-USD for system consistency"""
        if not market_id: return market_id
        c = market_id.upper()
        
        # Handle POL -> MATIC specifically
        if c.startswith('POL'):
            c = c.replace('POL', 'MATIC')
            
        if c.endswith('USDT'):
            return f"{c[:-4]}-USD"
        if c.endswith('TWD'):
            return f"{c[:-3]}-TWD"
        if '-' not in c:
            return f"{c}-USD"
        return c

    @staticmethod
    def _sync_max_data(user_id: str, real_logs: list):
        creds = get_user_credentials(user_id)
        if not creds.get("max_api_key"):
            return real_logs
            
        try:
            max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
            
            # Fetch Active Orders
            remote_orders = max_api.get_orders(state="wait") or []
            print(f"[Sync] MAX: Found {len(remote_orders)} remote pending orders.")
            
            # Fetch Recent Trades (Filled)
            remote_trades = max_api.get_trades() or []
            print(f"[Sync] MAX: Found {len(remote_trades)} remote execution records.")
            
            # Reconciliation Logic:
            # a) Identify existing real trade IDs in local logs
            local_ids = {str(L.get("trade_id")) for L in real_logs if L.get("trade_id")}
            
            # b) Add missing Pending orders from broker
            for o in remote_orders:
                tid = str(o.get('id'))
                if tid not in local_ids:
                    market_id = o.get('market', 'btcusdt')
                    symbol = ReconciliationService._normalize_crypto_symbol(market_id)
                    print(f"[Sync] Found missing MAX order: {tid} ({symbol})")
                    real_logs.append({
                        "trade_id": tid,
                        "symbol": symbol,
                        "name": get_symbol_name(symbol, "CRYPTO"),
                        "action": "Buy" if o.get('side') == 'buy' else "Sell",
                        "qty": float(o.get('volume', 0)),
                        "price": float(o.get('price', 0)),
                        "market": "CRYPTO",
                        "is_simulation": False,
                        "entry_type": "PENDING",
                        "status": "OPEN",
                        "timestamp": o.get('created_at', datetime.now().isoformat())
                    })
                    local_ids.add(tid)

            # c) Add missing Filled history from broker
            for t in remote_trades:
                tid = str(t.get('id'))
                # For history, we check if this specific trade record exists
                if tid not in local_ids:
                     # Check if it was a PENDING order we already have
                     order_id = str(t.get('order_id'))
                     existing_pending = next((L for L in real_logs if str(L.get("trade_id")) == order_id and L.get("entry_type") == "PENDING"), None)
                     
                     if existing_pending:
                         # Update existing pending to history
                         print(f"[Sync] Updating local pending {order_id} to FILLED via trade {tid}")
                         existing_pending["entry_type"] = "HISTORY"
                         existing_pending["status"] = "FILLED"
                         existing_pending["price"] = float(t.get('price', existing_pending["price"]))
                         existing_pending["timestamp"] = t.get('created_at', existing_pending["timestamp"])
                     else:
                         # New history item
                         market_id = t.get('market', 'UNKNOWN')
                         symbol = ReconciliationService._normalize_crypto_symbol(market_id)
                         print(f"[Sync] Found missing MAX trade record: {tid} ({symbol})")
                         real_logs.append({
                            "trade_id": tid, # or order_id
                            "symbol": symbol,
                            "name": get_symbol_name(symbol, "CRYPTO"),
                            "action": "Buy" if t.get('side') == 'buy' else "Sell",
                            "qty": float(t.get('volume', 0)),
                            "price": float(t.get('price', 0)),
                            "market": "CRYPTO",
                            "is_simulation": False,
                            "entry_type": "HISTORY",
                            "status": "FILLED",
                            "timestamp": t.get('created_at', datetime.now().isoformat())
                         })
                         local_ids.add(tid)
            
        except Exception as e:
            print(f"[Sync] MAX Sync Error: {e}")
            
        return real_logs

    @staticmethod
    def _sync_shioaji_data(user_id: str, real_logs: list):
        try:
            # 1. Fetch Orders (Shioaji list_trades returns both pending and history)
            results = ShioajiService.get_orders(user_id)
            if not results:
                return real_logs
                
            local_ids = {str(L.get("trade_id")) for L in real_logs if L.get("trade_id")}
            
            for item in results:
                tid = str(item.get("trade_id"))
                if tid not in local_ids:
                    print(f"[Sync] Found missing Shioaji item: {tid}")
                    status = item.get("status", "Unknown")
                    
                    entry_type = "PENDING"
                    if "Filled" in status: entry_type = "HISTORY"
                    elif "Cancelled" in status: entry_type = "HISTORY"
                    
                    real_logs.append({
                        "trade_id": tid,
                        "symbol": item.get("symbol"),
                        "name": get_symbol_name(item.get("symbol"), "TW"), # Default to TW for now
                        "action": item.get("action"),
                        "qty": float(item.get("qty", 0)),
                        "price": float(item.get("price", 0)),
                        "market": "TW", # Detection needed if multi-market
                        "is_simulation": False,
                        "entry_type": entry_type,
                        "status": "FILLED" if "Filled" in status else ("CANCELLED" if "Cancelled" in status else "OPEN"),
                        "timestamp": item.get("time", datetime.now().isoformat())
                    })
                    local_ids.add(tid)
                else:
                    # Update status of existing pending
                    local_item = next((L for L in real_logs if str(L.get("trade_id")) == tid), None)
                    if local_item and local_item.get("entry_type") == "PENDING":
                        remote_status = item.get("status", "")
                        if "Filled" in remote_status:
                            local_item["entry_type"] = "HISTORY"
                            local_item["status"] = "FILLED"
                        elif "Cancelled" in remote_status:
                            local_item["entry_type"] = "HISTORY"
                            local_item["status"] = "CANCELLED"

        except Exception as e:
            print(f"[Sync] Shioaji Sync Error: {e}")
            
        return real_logs

reconciliation_service = ReconciliationService()
