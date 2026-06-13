import sys
import os
sys.path.append(os.getcwd())
from api.services.storage_service import get_all_users_for_notifications, get_all_users_with_auto_trade
from api.services.strategy_accounts import list_strategy_accounts

print("Notifications:", get_all_users_for_notifications())
print("Auto Trade Users:", get_all_users_with_auto_trade())
print("Strategy Accounts:", [s["user_id"] for s in list_strategy_accounts()])
