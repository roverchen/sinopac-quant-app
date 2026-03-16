# Sinopac Quant Pro (金融商品市場報明牌系統)

[![Version](https://img.shields.io/badge/version-2.1.68-blue.svg)](REVISIONS.md)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()

Sinopac Quant Pro 是一個強大的多市場資產篩選與自動化交易系統，支援 **台股 (TW)**、**美股 (US)** 以及 **加密貨幣 (Crypto)**。本系統結合了動態權重配置策略、技術面計分引擎與基本面濾網，為量化交易者提供從選股、分析到下單的一站式解決方案。

---

## 🚀 核心特點 (Core Features)

### 1. 多市場全方位支援
- **台股 & 美股**：整合 Shioaji (永豐金) API，提供高速行情抓取與下單功能。
- **加密貨幣**：深度整合 MAX 交易所，支援 TWD 交易對優先策略與實時損益追蹤。
- **混合數據源**：結合 Yahoo Finance 公開數據與券商 API，兼顧數據廣度與交易深度。

### 2. 量化選股引擎 (Quant Engine)
系統採用「權重動態配置」策略，透過兩大維度進行評分（滿分 100）：
- **🛡️ 價值防禦 (Value Score)**：尋找跌深、具備安全邊際的標的。結合年線/季線乖離率、位階百分比與成交量動能。
- **📈 強勢拉回 (Pullback Score)**：順勢交易策略，鎖定月線附近回檔的強勢股，並結合 MACD 金叉與 0 軸濾鏡。
- **動態偏好調整**：使用者可透過滑桿自定義「成長 ↔ 防禦」比重，系統將即時重新計算綜合分數。

### 3. 無情的交易機器人 (Automated Trading)
- **定時海選進場**：每日定時自動掃描全市場，挑選 Top 1 標的自動模擬進場。
- **紀律出場機制**：內建自動停損 (≤ -5%) 與自動停利 (≥ +20%) 邏輯，嚴格執行交易紀律。

### 4. 深度優化與安全
- **憑證加密存儲**：所有 API Key、PFX 憑證均採加密處理，支援多人獨立帳戶環境。
- **快取備援機制**：實作雲端環境防封鎖保護、UARotation 以及海選快取共享機制。
- **行動端適應**：全站具備 RWD 響應式佈局，支援手機與平板流暢操作。

---

## 🛠️ 技術架構 (Tech Stack)

- **Frontend**: React 18, Vite, Tailwind CSS, Framer Motion (動態視覺效果), Lucide React (圖標).
- **Backend**: FastAPI (Python 3.11), Uvicorn.
- **Data & APIs**: 
  - [Shioaji](https://github.com/Sinopac/shioaji) (永豐證券 API)
  - [Max-Exchange](https://max.maicoin.com/) (Maicoin MAX API)
  - [FinMind](https://finmind.github.io/) (台股基本面數據)
  - [Yahoo Finance](https://pypi.org/project/yfinance/) (歷史 K 線與即時價)

---

## 📦 安裝與啟動 (Getting Started)

### 本地開發環境
1. **設定環境變數**：建立 `.env` 檔案並配置必要金鑰。
2. **安裝依賴**：
   ```bash
   pip install -r requirements.txt
   cd web && npm install && cd ..
   ```
3. **啟動服務**：
   ```bash
   chmod +x run_local.sh
   ./run_local.sh
   ```
   - 後端 API: `http://localhost:8000`
   - 前端 UI: `http://localhost:5173`

### 雲端部署 (Docker)
本專案支援 Docker 容器化部署，可直接發布至 Google Cloud Run：
```bash
gcloud builds submit --config cloudbuild.yaml .
```

---

## 變更紀錄 (Revision History)

關於系統的歷次更新細節、Bug Fix 以及版本迭代說明，請參閱：
👉 **[REVISIONS.md](REVISIONS.md)**

---

## ⚖️ 免責聲明 (Disclaimer)

本系統僅供學術研究與模擬交易參考，不構成任何形式的投資建議。使用者在本系統內所進行的任何實盤下單行為，其後果由使用者自行承擔。
