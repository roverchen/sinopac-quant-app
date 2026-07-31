from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import auth, quant, trade, diag
import uvicorn
import os
import sys
import certifi
import time

# Set timezone to Asia/Taipei to ensure scheduler runs on Taiwan Time (UTC+8)
os.environ['TZ'] = 'Asia/Taipei'
if hasattr(time, 'tzset'):
    time.tzset()

# Fix SSL Certificate Verification Error on Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Ensure project root is in Python path for subpackage imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title="Sinopac Quant Pro API",
    description="Professional backend for quantitative stock analysis and trading.",
    version="v2.8.0"
)

@app.on_event("startup")
async def startup_event():
    from api.services.trade_engine import engine
    engine.start()
    from api.services.auto_trade_service import robot
    robot.start()
    print("[Main] Background services started.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def root():
    return {"message": "Sinopac Quant Pro API", "version": "v2.8.0"}

app.include_router(quant.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(trade.router, prefix="/api")
app.include_router(diag.router, prefix="/api")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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

static_path = "static"
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
