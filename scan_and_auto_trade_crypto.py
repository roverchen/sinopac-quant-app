import asyncio
import os
from api.services.quant_service import run_market_scan, get_cached_pool
from api.services.shioaji_service import ShioajiService

async def main():
    USER_EMAIL = "rover.k.chen@gmail.com"
    MARKET = "CRYPTO"
    TARGET_TWD = 1000 # 預設下單 1000 台幣
    
    print(f"--- [AutoTrade] Starting {MARKET} scan ---")
    await run_market_scan(MARKET)
    
    pool = get_cached_pool(MARKET)
    if not pool or not pool.get("results"):
        print("Scan failed or returned no results.")
        return
        
    results = pool["results"]
    # 取得評分最高的標的
    top_1 = results[0]
    
    # Handle Pydantic or Dict
    def get_val(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    symbol = get_val(top_1, "symbol")
    name = get_val(top_1, "name")
    price = get_val(top_1, "price")
    score = get_val(top_1, "score")
    
    print(f"Top Candidate: {symbol} ({name}) | Score: {score} | Price: {price} TWD")
    
    if not price or price <= 0:
        print("Invalid price, skipping trade.")
        return
        
    # 計算數量 (以 1000 台幣為基準)
    qty = round(TARGET_TWD / price, 4)
    
    print(f"Calculated Qty for {TARGET_TWD} TWD: {qty}")
    
    if qty <= 0:
        print("Quantity too small, skipping trade.")
        return

    from api.services.shioaji_service import is_usd_denominated
    from api.services.trade_engine import engine
    order_price = price
    if is_usd_denominated(symbol, "CRYPTO"):
        rate = engine._get_cached_exchange_rate()
        order_price = price / rate

    print(f"--- [AutoTrade] Placing REAL order for {symbol} ---")
    res = ShioajiService.place_order(
        USER_EMAIL,
        symbol,
        qty,
        order_price,
        action="Buy",
        is_simulation=False,
        name=name
    )
    
    print(f"Order Result: {res}")

if __name__ == "__main__":
    asyncio.run(main())
