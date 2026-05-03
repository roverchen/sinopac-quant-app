import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.getcwd())

from api.services.storage_service import get_user_trade_logs

logs = get_user_trade_logs("system_auto")
print(json.dumps(logs[:5], indent=2, ensure_ascii=False))
