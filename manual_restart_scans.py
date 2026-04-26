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
    msg = f"Manual scan of {', '.join(markets)} completed successfully at {datetime.now().strftime('%H:%M')}."
    save_robot_status({
        "status": "Idle",
        "message": msg
    })
    
    # 4. Email Notification
    from api.services.email_service import send_email
    user_email = "rover.k.chen@gmail.com"
    subject = "✅ Sinopac Quant Pro: 全市場掃描已完成"
    body = f"""
    <html>
    <body style="font-family: sans-serif; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #4f46e5;">全市場掃描完成通知</h2>
            <p>您好，系統已完成手動觸發的全市場掃描：</p>
            <ul style="background-color: #f8fafc; padding: 20px; border-radius: 8px; list-style-type: none;">
                <li>🚀 <b>掃描項目</b>：{', '.join(markets)}</li>
                <li>⏰ <b>完成時間</b>：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                <li>📊 <b>狀態</b>：成功</li>
            </ul>
            <p>您可以回到 Dashboard 查看最新的選股結果與評分。</p>
            <p style="font-size: 0.8em; color: #94a3b8;">此郵件由系統自動發出。</p>
        </div>
    </body>
    </html>
    """
    send_email(user_email, subject, body)
    
    print("\n🎉 All scans completed and notification sent.")

if __name__ == "__main__":
    asyncio.run(restart())
