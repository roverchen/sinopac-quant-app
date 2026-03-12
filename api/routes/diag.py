from fastapi import APIRouter, Depends
import logging
from typing import List, Dict
from datetime import datetime
from api.routes.auth import get_current_user

router = APIRouter(prefix="/diag", tags=["diagnostics"])

# 全域日誌緩衝區
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

# 註冊日誌處理器
root_logger = logging.getLogger()
handler = DiagnosticHandler()
handler.setLevel(logging.WARNING) # 只記錄警告與錯誤
root_logger.addHandler(handler)

@router.get("/logs")
async def get_logs(current_user: str = Depends(get_current_user)):
    """取得最近的系統日誌 (需要權限)"""
    return {
        "logs": log_buffer,
        "system_info": {
            "version": "v2.0.6",
            "environment": "production",
            "status": "healthy" if not any(l["level"] == "ERROR" for l in log_buffer) else "warning"
        }
    }

@router.post("/clear")
async def clear_logs(current_user: str = Depends(get_current_user)):
    """清空日誌緩衝區"""
    log_buffer.clear()
    return {"status": "success"}
