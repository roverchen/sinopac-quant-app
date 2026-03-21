import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# SMTP Configuration from Environment Variables
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
# [v2.2.5] Attempting to display name only as requested
SMTP_FROM = os.getenv("SMTP_FROM", "Sinopac Quant Pro (no-reply)")

def send_email(to_email: str, subject: str, body_html: str):
    """
    Sends an HTML email using SMTP.
    """
    if not SMTP_USER or not SMTP_PASS:
        print("[EmailService] SMTP credentials missing. Skipping email.")
        return False

    msg = MIMEMultipart()
    msg['From'] = SMTP_FROM
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)
        server.quit()
        print(f"[EmailService] Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"[EmailService] Failed to send email to {to_email}: {e}")
        return False

def notify_trade(to_email: str, symbol: str, action: str, price: float, market: str, score: float = 0):
    """
    Convenience function to notify about a trade.
    """
    subject = f"📈 Sinopac Quant Pro: {action} Order Executed for {symbol}"
    
    action_zh = "買入" if action.lower() == "buy" else "賣出"
    color = "#10b981" if action.lower() == "buy" else "#f43f5e"
    
    html = f"""
    <html>
    <body style="font-family: sans-serif; color: #1e293b; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
            <h2 style="color: #4f46e5; border-bottom: 2px solid #f1f5f9; padding-bottom: 10px;">智能交易通知 (Auto-Trade)</h2>
            <p>您的自動交易機器人剛剛執行了一筆操作：</p>
            
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <table style="width: 100%;">
                    <tr>
                        <td style="font-weight: bold; width: 100px;">標的：</td>
                        <td style="font-size: 1.2em; font-weight: 900;">{symbol}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">市場：</td>
                        <td>{market}</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">動作：</td>
                        <td style="color: {color}; font-weight: bold; font-size: 1.1em;">{action_zh} ({action})</td>
                    </tr>
                    <tr>
                        <td style="font-weight: bold;">成交價：</td>
                        <td style="font-family: monospace; font-weight: bold;">${price}</td>
                    </tr>
                    {f"<tr><td style='font-weight: bold;'>策略評分：</td><td>{score}</td></tr>" if score else ""}
                </table>
            </div>
            
            <p style="font-size: 0.9em; color: #64748b;">
                時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}<br>
                此郵件由系統自動發出，請勿直接回覆。
            </p>
            
            <div style="margin-top: 30px; border-top: 1px solid #f1f5f9; padding-top: 10px; font-size: 0.8em; color: #94a3b8; text-align: center;">
                <a href="https://quant-pro.roverchen.com/settings" style="color: #4f46e5; text-decoration: none;">取消訂閱或修改通知設定</a>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email(to_email, subject, html)
