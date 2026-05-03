from fastapi import APIRouter, Depends
import logging
import os
from typing import List, Dict
from datetime import datetime
from api.routes.auth import get_current_user

router = APIRouter(prefix="/diag", tags=["diagnostics"])

# Global log buffer
MAX_LOGS = 50
log_buffer: List[Dict] = []

class DiagnosticHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module
            }
            log_buffer.insert(0, log_entry)
            if len(log_buffer) > MAX_LOGS:
                log_buffer.pop()
        except Exception:
            pass

# Register log handler
root_logger = logging.getLogger()
handler = DiagnosticHandler()
handler.setLevel(logging.WARNING) 
root_logger.addHandler(handler)

@router.get("/logs")
async def get_logs(current_user: str = Depends(get_current_user)):
    from api.services.shioaji_service import shioaji_service
    acc_info = shioaji_service.get_account_info(current_user)
    
    return {
        "logs": log_buffer,
        "system_info": {
            "version": "v2.7.6",
            "environment": "production",
            "status": "healthy" if not any(l["level"] == "ERROR" for l in log_buffer) else "warning",
            "shioaji_status": acc_info.get("status", "disconnected") if acc_info else "disconnected"
        }
    }

@router.post("/clear")
async def clear_logs(current_user: str = Depends(get_current_user)):
    log_buffer.clear()
    return {"status": "success"}

@router.post("/trigger_auto_trade")
async def trigger_auto_trade(market: str = "TW", strategy_user_id: str = "system_auto", current_user: str = Depends(get_current_user)):
    """Manually trigger the AutoRobot cycle for testing"""
    from api.services.auto_trade_service import robot
    import threading
    
    # Run in background to not block API
    threading.Thread(target=robot.perform_daily_trade, kwargs={"market_type": market, "strategy_user_id": strategy_user_id}, daemon=True).start()
    
    return {
        "status": "triggered",
        "market": market,
        "strategy_user_id": strategy_user_id,
        "message": f"Auto-trade cycle initiated for {strategy_user_id} on {market}. Check Trade History or Diag Logs for updates."
    }

@router.get("/wakeup")
async def wakeup(token: str = ""):
    """Special endpoint for Cloud Scheduler pulsars to wake up the system and run auto-trade logic.
    Awaits full execution to prevent Cloud Run from scaling down prematurely.
    """
    # Simple security token check to prevent unauthorized spamming of scans
    # If not set in env, it's open for now (can be added later for security)
    expected_token = os.getenv("WAKEUP_TOKEN", "")
    if expected_token and token != expected_token:
        return {"status": "unauthorized"}

    from api.services.auto_trade_service import robot
    print(f"[Diag] Wakeup pulse received @ {datetime.now()}")
    
    # [v2.7.5] Run the logic in a separate thread to avoid "RuntimeError: asyncio.run() from running loop"
    import threading
    worker = threading.Thread(target=robot.ensure_fresh_scans)
    worker.start()
    worker.join() # Await completion to keep Cloud Run alive
    
    return {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "message": "System wake-up successful. All scheduled tasks and makeup trades processed."
    }
