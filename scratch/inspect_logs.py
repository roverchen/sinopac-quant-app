import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs
from api.services.storage_service import get_user_settings
print("=== Settings ===")
print(get_user_settings("system_auto"))

logs = get_user_trade_logs("system_auto")
buy_logs = [l for l in logs if l.get("action") == "Buy" or l.get("entry_type") == "POSITION"]
print("=== Buy Logs ===")
print(json.dumps(buy_logs, indent=2, ensure_ascii=False))
