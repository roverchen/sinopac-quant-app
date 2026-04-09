import os
import sys
import asyncio
import certifi
from datetime import datetime

# Fix SSL Certificate Verification Error on Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import save_robot_status
from api.services.auto_trade_service import robot
from api.services.quant_service import run_market_scan

async def restart():
    print(f"--- [Manual Restart] {datetime.now()} ---")
    
    # 1. Reset status to Idle first
    save_robot_status({
        "status": "Idle",
        "message": "Manual restart initiated by user. Starting scans..."
    })
    print("Status reset to Idle.")

    # 2. Sequential Scans (CRYPTO first for fast feedback)
    markets = ["CRYPTO", "TW", "US"]
    
    for m in markets:
        print(f"\n🚀 Starting scan for {m}...")
        save_robot_status({
            "status": "Scanning",
            "message": f"Manual scan in progress for {m}..."
        })
        try:
            await run_market_scan(m)
            print(f"✅ {m} scan completed.")
        except Exception as e:
            print(f"❌ {m} scan failed: {e}")
            save_robot_status({
                "status": "Error",
                "message": f"{m} scan failed: {str(e)}"
            })

    # 3. Final Status Update
    save_robot_status({
        "status": "Idle",
        "message": f"Manual scan of {', '.join(markets)} completed successfully at {datetime.now().strftime('%H:%M')}."
    })
    print("\n🎉 All scans completed successfully.")

if __name__ == "__main__":
    asyncio.run(restart())
