from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from api.routes import auth, quant, trade
import uvicorn
import os

app = FastAPI(
    title="Sinopac Quant Pro API",
    description="Professional backend for quantitative stock analysis and trading.",
    version="1.0.1" # Incrementing to verify deployment
)

# 配置 CORS，允許前端訪問
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 生產環境應限制特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 註冊路由
app.include_router(quant.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(trade.router, prefix="/api")

# 靜態檔案掛載 (React Build 結果)
# 優先檢查 static 目錄是否存在，若存在則掛載
static_path = "static"
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
