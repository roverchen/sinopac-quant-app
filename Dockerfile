# Stage 1: Build React Frontend
FROM node:20-slim AS build-stage
WORKDIR /app/web
COPY web/package*.json ./
RUN npm install
COPY web/ ./
RUN npm run build

# Stage 2: Build Python Backend & Serve
FROM python:3.11-slim
WORKDIR /app

# 安裝系統依賴 (如 Shioaji 可能需要的)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 依賴
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製後端程式碼
COPY api/ ./api/
# 複製基礎工具 (sinopac_api.py, max_api.py 等)
COPY sinopac_api.py max_api.py ./

# 從第一階段複製編譯好的前端靜態檔案
COPY --from=build-stage /app/web/dist ./static

# 設定環境變數
ENV PORT=8080
ENV GOOGLE_CLOUD_PROJECT=sinopac-quant-app

# 啟動命令
# 使用 uvicorn 啟動 FastAPI，並將埠號與環境變數對接
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
