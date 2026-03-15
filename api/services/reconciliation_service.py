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
            real_trades = ShioajiService.get_broker_trades(user_id)
            for t in real_trades:
                self._merge_shioaji_trade(logs, t)
        except Exception as e:
            print(f"[Recon] Shioaji Sync Error: {e}")

        # 2. MAX (Crypto)
        if creds.get("max_api_key") and creds.get("max_api_secret"):
            try:
                max_api = MaxExchangeAPI(creds["max_api_key"], creds["max_api_secret"])
                # Fetch recent trades
                max_trades = max_api.get_trades()
                if isinstance(max_trades, list):
                    for mt in max_trades:
                        self._merge_max_trade(logs, mt)
            except Exception as e:
                print(f"[Recon] MAX Sync Error: {e}")

        final_count = len(logs)
        print(f"[Recon] Sync finished for {user_id}. Added {final_count - initial_count} new records.")

        if final_count != initial_count:
            save_user_trade_logs(user_id, logs)
        
        return {
            "status": "success",
            "added": final_count - initial_count,
            "total": final_count
        }

    def _merge_shioaji_trade(self, logs, trade):
        trade_id = str(trade.order.id)
        # Check if already exists in logs
        if any(L.get("trade_id") == trade_id for L in logs):
            return

        # Determine market
        symbol = trade.contract.code
        market = "TW"
        if len(symbol) > 4 and not symbol.isdigit():
            market = "US"

        print(f"[Recon] Merging missing Shioaji trade: {symbol} ID:{trade_id}")
        
        new_entry = {
            "trade_id": trade_id,
            "symbol": symbol,
            "name": getattr(trade.contract, 'name', symbol),
            "action": "Buy" if "Buy" in str(trade.order.action) else "Sell",
            "qty": float(trade.order.quantity),
            "price": float(trade.order.price),
            "market": market,
            "is_simulation": False,
            "entry_type": "HISTORY",
            "status": "FILLED",
            "timestamp": str(trade.status.order_datetime) if hasattr(trade.status, 'order_datetime') else datetime.now().isoformat()
        }
        logs.append(new_entry)

    def _merge_max_trade(self, logs, mt):
        # MAX trades are executed trades
        trade_id = str(mt.get("id"))
        if any(L.get("trade_id") == trade_id for L in logs):
            return

        symbol = mt.get("market", "crypto").upper()
        # Convert btctwd -> BTC-TWD
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

recon_service = ReconciliationService()
