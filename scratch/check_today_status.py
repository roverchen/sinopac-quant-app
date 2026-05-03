import sys
import os
import json
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_robot_status, get_user_trade_logs

status = get_robot_status()
print(f"--- Robot Status ---")
print(json.dumps(status, indent=2))

print(f"\n--- Recent Trades (system_auto) ---")
logs = get_user_trade_logs("system_auto")
if logs:
    logs.sort(key=lambda x: str(x.get("timestamp", x.get("buy_time", ""))), reverse=True)
    for log in logs[:10]:
        ts = log.get("timestamp") or log.get("buy_time")
        symbol = log.get("symbol")
        market = log.get("market")
        print(f"[{ts}] {symbol} ({market})")
else:
    print("No logs found.")
