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
            
            # 1. Market Discovery: Identify which markets to check
            # We check markets related to: 
            # a) Assets currently in balance (with non-zero balance or locked)
            # b) Symbols in the user's watchlist
            relevant_currencies = set()
            balances = max_api.get_account_balance()
            if isinstance(balances, dict) and "error" not in balances:
                for curr, detail in balances.items():
                    if detail.get('balance', 0) > 0 or detail.get('locked', 0) > 0:
                        relevant_currencies.add(curr.lower())
            
            from api.services.storage_service import get_user_watchlist
            watchlist = get_user_watchlist(user_id) or []
            for item in watchlist:
                if item.startswith("CRYPTO:"):
                    code = item.split(":")[1].split("-")[0].lower()
                    relevant_currencies.add(code)
            
            # c) Currencies found in existing trade_logs
            for L in real_logs:
                sym = str(L.get("symbol", ""))
                if "-" in sym:
                    code = sym.split("-")[0].lower()
                    relevant_currencies.add(code)
            
            # Ensure major ones are always present
            relevant_currencies.add("btc")
            relevant_currencies.add("eth")
            relevant_currencies.add("dot") # Explicitly add DOT as requested
            
            # Fetch all available markets to match against relevant currencies
            all_markets = max_api.get_markets()
            markets_to_sync = []
            for m in all_markets:
                # If the base currency is interesting to us, we want to see its trades
                if m['base_unit'] in relevant_currencies:
                    markets_to_sync.append(m['id'])
            
            # Add defaults if nothing found
            if not markets_to_sync:
                markets_to_sync = ["btcusdt", "ethusdt"]
            
            markets_to_sync = list(set(markets_to_sync))
            print(f"[Sync] MAX: Discovered {len(markets_to_sync)} relevant markets for sync: {markets_to_sync[:5]}...")

            local_ids = {str(L.get("trade_id")) for L in real_logs if L.get("trade_id")}
            
            # 2. Iterate through markets to fetch orders and trades
            # Note: MAX API v2 typically requires 'market' for private order/trade endpoints
            for market_id in markets_to_sync:
                try:
                    # Fetch Active Orders
                    remote_orders = max_api.get_orders(market=market_id, state="wait") or []
                    if remote_orders:
                        print(f"[Sync] MAX: Found {len(remote_orders)} pending orders in {market_id}")
                    
                    for o in remote_orders:
                        tid = str(o.get('id'))
                        if tid not in local_ids:
                            symbol = ReconciliationService._normalize_crypto_symbol(market_id)
                            print(f"[Sync] Found missing MAX order: {tid} ({symbol})")
                            real_logs.append({
                                "trade_id": tid,
                                "symbol": symbol,
                                "name": get_symbol_name(symbol, "CRYPTO"),
                                "action": "Buy" if o.get('side') in ['buy', 'bid'] else "Sell",
                                "qty": float(o.get('volume', 0)),
                                "price": float(o.get('price', 0)),
                                "market": "CRYPTO",
                                "is_simulation": False,
                                "entry_type": "PENDING",
                                "status": "OPEN",
                                "timestamp": datetime.fromtimestamp(o.get('created_at')).isoformat() if isinstance(o.get('created_at'), int) else o.get('created_at'),
                                "order_time": datetime.now().isoformat() # Fallback order time if missing
                             })
                            local_ids.add(tid)

                    # Fetch Recent Trades (Filled)
                    remote_trades = max_api.get_trades(market=market_id) or []
                    for t in remote_trades:
                        tid = str(t.get('id'))
                        if tid not in local_ids:
                             order_id = str(t.get('order_id'))
                             existing_pending = next((L for L in real_logs if str(L.get("trade_id")) == order_id and L.get("entry_type") == "PENDING"), None)
                             
                             if existing_pending:
                                 print(f"[Sync] Updating local pending {order_id} to FILLED via trade {tid}")
                                 existing_pending["entry_type"] = "HISTORY"
                                 existing_pending["status"] = "FILLED"
                                 existing_pending["price"] = float(t.get('price', existing_pending["price"]))
                                 # [v2.1.65] Record fill_time and preserve timestamp as order_time fallback
                                 if "order_time" not in existing_pending:
                                     existing_pending["order_time"] = existing_pending.get("timestamp")
                                 existing_pending["fill_time"] = datetime.fromtimestamp(t.get('created_at')).isoformat() if isinstance(t.get('created_at'), int) else t.get('created_at')
                                 existing_pending["timestamp"] = existing_pending["fill_time"]
                             else:
                                 symbol = ReconciliationService._normalize_crypto_symbol(market_id)
                                 print(f"[Sync] Found missing MAX trade record: {tid} ({symbol})")
                                 real_logs.append({
                                    "trade_id": tid,
                                    "symbol": symbol,
                                    "name": get_symbol_name(symbol, "CRYPTO"),
                                    "action": "Buy" if t.get('side') in ['buy', 'bid'] else "Sell",
                                    "qty": float(t.get('volume', 0)),
                                    "price": float(t.get('price', 0)),
                                    "market": "CRYPTO",
                                    "is_simulation": False,
                                    "entry_type": "HISTORY",
                                    "status": "FILLED",
                                    "timestamp": datetime.fromtimestamp(t.get('created_at')).isoformat() if isinstance(t.get('created_at'), int) else t.get('created_at'),
                                    "order_time": datetime.fromtimestamp(t.get('created_at')).isoformat() if isinstance(t.get('created_at'), int) else t.get('created_at'),
                                    "fill_time": datetime.fromtimestamp(t.get('created_at')).isoformat() if isinstance(t.get('created_at'), int) else t.get('created_at')
                                 })
                                 local_ids.add(tid)
                except Exception as market_err:
                    print(f"[Sync] Error syncing market {market_id}: {market_err}")
            
        except Exception as e:
            print(f"[Sync] MAX Overall Sync Error: {e}")
            
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
                        "timestamp": item.get("time", datetime.now().isoformat()),
                        "order_time": item.get("time", datetime.now().isoformat()),
                        "fill_time": item.get("time") if "Filled" in status else None
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
                            if "order_time" not in local_item:
                                local_item["order_time"] = local_item.get("timestamp")
                            local_item["fill_time"] = item.get("time", datetime.now().isoformat())
                        elif "Cancelled" in remote_status:
                            local_item["entry_type"] = "HISTORY"
                            local_item["status"] = "CANCELLED"

        except Exception as e:
            print(f"[Sync] Shioaji Sync Error: {e}")
            
        return real_logs

reconciliation_service = ReconciliationService()
