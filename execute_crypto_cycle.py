import os
import sys
import asyncio
import certifi

# Step 1: Fix SSL Certificate Verification Error on Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Step 2: Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.quant_service import run_market_scan, results_cache
from api.services.auto_trade_service import robot

async def execute_crypto():
    market = "CRYPTO"
    print(f"🚀 Starting Manual Crypto Cycle...")
    
    # Force refresh: clear local cache
    if market in results_cache:
        results_cache[market] = None
        print(f"  - Local cache cleared for {market}")
    
    print(f"  - Initiating fresh scan for {market} (v2.1.52 logic)...")
    await run_market_scan(market)
    
    print(f"  - Initiating trade execution for {market}...")
    # perform_daily_trade is synchronous inside the class, but we call it here
    robot.perform_daily_trade(market)
    
    print("\n✅ Crypto scan and trade cycle triggered successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(execute_crypto())
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()
