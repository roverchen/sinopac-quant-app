import os
import sys
from datetime import datetime

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_robot_status, get_user_trade_logs

def check_status():
    print(f"--- [Status Check] {datetime.now()} ---")
    
    # 1. Check Robot Status
    status = get_robot_status()
    print("\n[Robot Status]:")
    if status:
        for k, v in status.items():
            print(f"  {k}: {v}")
    else:
        print("  No robot status found in storage (Firestore/Local).")

    # 2. Check Recent Trade Logs for system_auto
    print("\n[Recent Trade Logs (system_auto)]:")
    logs = get_user_trade_logs("system_auto")
    if logs:
        # Sort by timestamp descending
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        for log in logs[:5]: # Show last 5
            print(f"  - {log.get('timestamp')}: {log.get('market')} | {log.get('symbol')} | {log.get('action')} | {log.get('entry_type')} | Status: {log.get('status')}")
    else:
        print("  No trade logs found for system_auto.")

if __name__ == "__main__":
    check_status()
