import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs
logs = get_user_trade_logs("system_auto")
def get_time(item):
    return item.get("timestamp") or item.get("fill_time") or item.get("order_time") or ""

recent_logs = [l for l in logs if get_time(l) >= "2026-06-13"]
recent_logs.sort(key=get_time, reverse=True)
print(json.dumps(recent_logs, indent=2, ensure_ascii=False))
