import os
import sys
from datetime import datetime
import json

# Ensure project root is in Python path
sys.path.append(os.getcwd())

from api.services.storage_service import get_robot_status, get_user_trade_logs, get_user_settings, get_all_users_for_notifications

def troubleshoot_notification():
    print(f"--- [Notification Troubleshooting] {datetime.now()} ---")
    
    # 1. Check SMTP ENV (Values hidden, just existence)
    print("\n[Environment Check]:")
    for key in ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"]:
        val = os.getenv(key)
        status = "SET" if val else "MISSING"
        # Special check for SMTP_PASS format
        if key == "SMTP_PASS" and val:
            if len(val.replace(" ", "")) == 16:
                status += " (App Password format detected)"
        print(f"  {key}: {status}")

    # 2. Check User Settings (rover.k.chen@gmail.com is likely the user)
    # The Robot says self.user_id = "system_auto" but notifies specific users.
    email = "rover.k.chen@gmail.com"
    print(f"\n[User Settings for {email}]:")
    settings = get_user_settings(email)
    print(f"  email_notifications_enabled: {settings.get('email_notifications_enabled')}")
    print(f"  mirror_trading_confirmed: {settings.get('mirror_trading_confirmed')}")
    
    # Check if user is in notification targets
    targets = get_all_users_for_notifications()
    target_emails = [t[0] for t in targets]
    print(f"  Is in notification targets list: {email in target_emails}")

    # 3. Analyze Robot Activity today
    print("\n[Robot Execution Log Analysis]:")
    status = get_robot_status()
    print(f"  Last Status: {status.get('status')} - {status.get('message')}")
    print(f"  Last Updated: {status.get('last_updated')}")

    # 4. Check for recent BUY actions in system_auto logs
    print("\n[Recent Trades (system_auto)]:")
    logs = get_user_trade_logs("system_auto")
    # Filter for logs from 2026-03-31
    today_prefix = "2026-03-31"
    today_logs = [L for L in logs if L.get("timestamp", "").startswith(today_prefix)]
    
    if not today_logs:
        print("  No trade logs found for today yet.")
    else:
        for L in sorted(today_logs, key=lambda x: x.get("timestamp", ""), reverse=True):
            action = L.get('action') or L.get('trade_type', 'N/A')
            print(f"  - {L.get('timestamp')}: {L.get('market')} {L.get('symbol')} | Action: {action} | Entry: {L.get('entry_type')}")

    # 5. Check if it's currently running locally or not
    # Done via ps aux previously, confirmed NOT local.

if __name__ == "__main__":
    troubleshoot_notification()
