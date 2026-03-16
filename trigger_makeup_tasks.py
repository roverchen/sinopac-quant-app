import os
import sys
import asyncio
import certifi

# Step 1: Fix SSL Certificate Verification Error on Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Step 2: Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.quant_service import run_market_scan
from api.services.auto_trade_service import robot

async def perform_makeup():
    print("🚀 Starting Compensatory Tasks (Crypto & US)...")
    
    # Process CRYPTO
    market = "CRYPTO"
    print(f"\n[1/2] Processing {market}...")
    print(f"  - Initiating fresh scan for {market}...")
    await run_market_scan(market)
    print(f"  - Executing trading logic for {market}...")
    robot.perform_daily_trade(market)
    
    # Process US
    market = "US"
    print(f"\n[2/2] Processing {market}...")
    print(f"  - Initiating fresh scan for {market}...")
    await run_market_scan(market)
    print(f"  - Executing trading logic for {market}...")
    robot.perform_daily_trade(market)
    
    print("\n✅ All compensatory tasks completed successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(perform_makeup())
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during makeup tasks: {e}")
        import traceback
        traceback.print_exc()
