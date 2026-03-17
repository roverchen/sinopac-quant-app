import asyncio
from api.services.quant_service import run_market_scan

async def main():
    print("Starting manual CRYPTO market scan (TWD-centric)...")
    await run_market_scan(market_type="CRYPTO", defense_weight=0.5)
    print("CRYPTO scan complete.")

if __name__ == "__main__":
    asyncio.run(main())
