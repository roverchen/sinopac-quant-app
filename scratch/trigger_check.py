import sys
import os
import asyncio

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.auto_trade_service import robot
from datetime import datetime

print(f"Current Time: {datetime.now()}")
print("Triggering ensure_fresh_scans...")

# We need to run it in a way that doesn't block if possible, 
# but for a script, blocking is fine to see the result.
robot.ensure_fresh_scans()

print("\nScan/Trade check complete. Checking status again...")
from api.services.storage_service import get_robot_status
print(get_robot_status())
