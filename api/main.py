from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import auth, quant, trade, diag
import uvicorn
import os
import sys

# Ensure project root is in Python path for subpackage imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title="Sinopac Quant Pro API",
    description="Professional backend for quantitative stock analysis and trading.",
    version="1.1.9" 
)

@app.on_event("startup")
async def startup_event():
    # 啟動掛單撮合引擎
    from api.services.trade_engine import engine
    engine.start()
    
    # 啟動自動交易機器人
    from api.services.auto_trade_service import robot
    robot.start()
    print("[Main] Background services started.")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 1. Health Checks (Highest priority) ---
@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "healthy", "version": "1.1.9"}

# --- 2. API Routes ---
app.include_router(quant.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(diag.router, prefix="/api")

# --- 3. Exception Handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕捉所有未處理異常並返回包含 Traceback 的 JSON (開發者友善)"""
    error_trace = traceback.format_exc()
    print(f"CRITICAL ERROR: {str(exc)}\n{error_trace}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "traceback": error_trace,
            "path": request.url.path
        }
    )

# --- 4. Static Files (Lowest priority, catch-all) ---
static_path = "static"
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080) # Consistent with Cloud Run default
