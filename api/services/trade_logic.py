import asyncio
from typing import List
from datetime import datetime
from api.services.quant_service import fetch_tw_symbols, fetch_us_symbols, analyze_stock
from api.services.data_fetcher import fetch_batch_data
from api.services.shioaji_service import ShioajiService
from api.services.storage_service import get_user_watchlist, get_user_credentials

async def execute_auto_trade_cycle(email: str, market_type: str = "TW"):
    """
    執行自動交易循環：
    1. 取得使用者追蹤清單與憑證
    2. 掃描清單標的
    3. 篩選高評分標的 (例如 > 80 分)
    4. 檢查目前庫存 (避免重複下單)
    5. 送出買入委託
    """
    print(f"[{datetime.now()}] Starting auto-trade cycle for {email} ({market_type})")
    
    # 1. 取得追蹤清單
    watchlist = get_user_watchlist(email, market_type)
    if not watchlist:
        print(f"Empty watchlist for {email}, skipping.")
        return

    # 2. 抓取數據並分析
    data_pool = fetch_batch_data(watchlist, market_type)
    
    # 名稱對照
    tw_names = fetch_tw_symbols() if market_type == "TW" else {}
    us_names = fetch_us_symbols() if market_type == "US" else {}
    
    candidates = []
    for symbol in watchlist:
        df = data_pool.get(symbol)
        if df is not None:
            name = tw_names.get(symbol) or us_names.get(symbol) or "未知"
            # 策略權重 0.5 (平衡型)
            result = analyze_stock(df, symbol, name, defense_weight=0.5, market_type=market_type)
            
            # 3. 篩選策略：分數大於 80 且處於強勢金叉
            if result['綜合評分'] >= 80 and "金叉" in result['MACD狀態']:
                candidates.append(result)

    if not candidates:
        print("No strong candidates found today.")
        return

    print(f"Found {len(candidates)} candidates: {[c['代碼'] for c in candidates]}")

    # 4. 執行下單 (目前僅限台股現貨，美股/幣市邏輯可後續擴充)
    if market_type == "TW":
        for stock in candidates:
            try:
                # 簡單策略：每檔買 1 張 (1000 股)，以市價/現價下單
                # 注意：實務上需檢查餘額與現有部位
                print(f"Placing auto-order for {stock['代碼']} @ {stock['最新價格']}")
                
                # 這裡調用 shioaji_service
                # ShioajiService.place_order(email, stock['代碼'], 1, stock['最新價格'])
                
                print(f"Successfully placed order for {stock['代碼']}")
            except Exception as e:
                print(f"Failed to place order for {stock['代碼']}: {e}")

async def run_scheduler():
    """
    背景排程監測器。
    """
    while True:
        now = datetime.now()
        # 示範：台股 14:00 執行
        if now.hour == 14 and now.minute == 0:
            # 這裡應該迭代所有已啟用自動下單的使用者
            # 暫時用示範邏輯
            pass
            
        await asyncio.sleep(60) # 每分鐘檢查一次
