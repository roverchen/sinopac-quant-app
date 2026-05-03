import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs

logs = get_user_trade_logs("system_auto")
if logs:
    # Sort by timestamp
    logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    print("Recent system_auto Trade Details:")
    for log in logs[:3]:
        print(f"\nTime: {log.get('timestamp')}")
        print(f"Action: {log.get('action')}")
        print(f"Symbol: {log.get('symbol')}")
        print(f"Market: {log.get('market')}")
        print(f"Price: {log.get('price')}")
        print(f"Score: {log.get('score')}")
        print(f"Reason: {log.get('reason')}")
