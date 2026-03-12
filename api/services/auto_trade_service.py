import time
import threading
import schedule
from datetime import datetime
from api.services.quant_service import run_market_scan, get_cached_pool
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_mock_positions, save_user_mock_positions, get_user_trade_history, save_user_trade_history

class AutoRobot:
    def __init__(self):
        self.user_id = "system_auto"
        self.running = False
        self.thread = None

    def start(self):
        if not self.running:
            self.running = True
            # Setup Schedule
            # README: US 06:00, TW 14:00, Crypto 23:05
            schedule.every().day.at("06:05").do(self.perform_daily_trade, market_type="US")
            schedule.every().day.at("14:05").do(self.perform_daily_trade, market_type="TW")
            schedule.every().day.at("23:10").do(self.perform_daily_trade, market_type="CRYPTO")
            # 出場檢查 (每小時檢查一次，或是由 MatchingEngine 負責)
            schedule.every(30).minutes.do(self.check_exits)
            
            self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self.thread.start()
            print(f"[AutoRobot] Started for {self.user_id}")

    def _run_scheduler(self):
        while self.running:
            schedule.run_pending()
            time.sleep(60)

    def perform_daily_trade(self, market_type):
        print(f"[AutoRobot] Running daily scan for {market_type}...")
        try:
            # 執行海選 (如果是凌晨 6 點，昨天的資料可能還在，但也沒關係)
            # 這裡我們直接抓快取的 Pool (因為海選可能已經由系統 cron 跑過，或者我們這時再跑一次)
            pool = get_cached_pool(market_type)
            if not pool or not pool.get("results"):
                # 如果沒快取，在此刻跑一次
                print(f"[AutoRobot] No cache found for {market_type}, starting new scan...")
                run_market_scan(market_type)
                pool = get_cached_pool(market_type)

            results = pool.get("results", [])
            if not results:
                print(f"[AutoRobot] No results found for {market_type} after scan.")
                return

            # 挑選 Top 1
            top_1 = results[0]
            # README 規則：使用建議買價 (entry_price)
            entry_price = getattr(top_1, 'entry_price', top_1.最新價格)
            print(f"[AutoRobot] Top 1 found: {top_1.代碼} ({top_1.名稱}) | Entry: {entry_price}")
            
            # 執行買入 (台股買 1 張, 美股/Crypto 視價格定)
            qty = 1000 if market_type == "TW" else (10 if market_type == "US" else 0.1)
            
            ShioajiService.place_order(
                self.user_id, 
                top_1.代碼, 
                qty, 
                entry_price, 
                action="Buy", 
                is_simulation=True
            )
            print(f"[AutoRobot] Order placed for {top_1.代碼}")
        except Exception as e:
            print(f"[AutoRobot] Scan/Order Error: {e}")

    def check_exits(self):
        """
        README: 觸碰到 TP +20% 或 SL -5% 時，全自動強制平倉。
        """
        print(f"[AutoRobot] Checking exits for {self.user_id}...")
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
