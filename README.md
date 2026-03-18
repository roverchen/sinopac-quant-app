# Sinopac Quant Pro (股市報明牌)

[![Version](https://img.shields.io/badge/version-2.1.86-blue.svg)](REVISIONS.md)
---

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
- **🛡️ 價值防禦 (Value Score)**：尋找跌深、具備安全邊際的標的。
  - **位階百分比**：計算當前價位在過去 52 週的相對高低位置。位階越低（越接近年線底部）分數越高。
  - **乖離率支撐**：判定股價是否回落至年線/季線支撐區（±5%），提供防禦買點。
  - **成交量動能**：偵測是否出現 1.2 倍以上的攻擊量，確認低檔有資金進場承接。
- **📈 強勢拉回 (Pullback Score)**：順勢交易策略，鎖定月線附近回檔的強勢股，並結合 MACD 金叉與 **0 軸濾鏡**。
  - **0 軸濾鏡機制**：利用 MACD 的 0 軸作為多空趨勢的分水嶺。系統僅在 MACD 快慢線均位於 0 軸上方（多頭強勢區）時，才將其視為高勝率的「強勢趨勢回檔」並給予最高加分，藉此過濾掉空頭趨勢下不穩定的低位反彈。
- **動態偏好調整**：使用者可透過滑桿自定義「成長 ↔ 防禦」比重，系統將即時重新計算綜合分數。

### 3. 進階跟單與自動交易 (Advanced Mirror Trading)
- **獨立系統帳戶**：自動交易是由 `system_auto` 帳號執行，與個人帳號分離。您可以在「交易環境控管」中切換至 **「系統」** 標籤查看其持倉。
- **時區精確鎖定排程**：系統強制鎖定 `Asia/Taipei` 時區，每日於 US (06:10)、TW (14:10)、Crypto (23:15) 自動執行海選。
- **預算與策略比例分配**：實盤跟單支援設定 **「單筆跟單總權重 (Total Allocation)」** 作為預算上限，並透過 **「策略比例 (Strategy Ratio)」** 自由調配價值與拉回策略的佔比。
- **多重安全鎖**：內建單筆交易最高金額上限 (Max Order Limit)、安全宣告彈窗，以及嚴謹的自動停損/停利邏輯，嚴格控制下單風險。
- **郵件自動通知**：當系統自動觸發買入與賣出動作時，將會即時發送 Email 至有開啟通知的使用者信箱。

### 4. 深度優化與安全
- **憑證加密存儲**：所有 API Key、PFX 憑證均採加密處理，支援多人獨立帳戶環境。
- **快取備援機制**：實作雲端環境防封鎖保護、UARotation 以及海選快取共享機制。
- **行動端適應**：全站具備 RWD 響應式佈局，支援手機與平板流暢操作。

---

## 📊 數據策略 (Data Strategy)

系統採取 **「混合雲端數據策略 (Hybrid Data Strategy)」**，以平衡開發成本與交易精準度：

### 1. Yahoo Finance：量化分析的「大數據骨幹」
*   **角色**：擔任 **1-year 歷史數據** 的核心供應源，用於計算 MA、MACD 與相對位階。
*   **優勢**：無需各別券商 API 限制，即可高效完成全市場（如 2,000+ 台股）的日線掃描。
*   **撮合基礎**：虛擬帳戶的 **「模擬撮合引擎 (Simulation Matcher)」** 均以 Yahoo Finance 的收盤價作為即時行情參考，實現無成本的策略驗證。

### 2. MAX & 幣安 (Crypto Strategy)：全球價格與在地交易
*   **幣安 (Binance) 角色**：作為全球最大的流動性池，系統透過 Yahoo Finance 的 `[SYMBOL]-USD` 接口間接引用幣安定價，確保分析採用的是最具代表性的全球市價。
*   **MAX 交易所角色**：擔任 **「在地實盤出口」**。系統整合 MAX API 管理 TWD 與加密貨幣的資金，並實作 **USD/TWD 匯率換算機制** (自動抓取最新美元匯率)，讓全球定價與在地 TWD 資產能無縫接軌。
*   **數據補全**：對於 MAX 上特有的 TWD 交易對，系統會自動在 Yahoo (USD 全球價) 與 MAX (實體交易介面) 間自動進行標的對齊與換算。

---

## 📈 交易機制說明 (Trading Lifecycle)

系統區分為 **「虛擬模擬 (Simulation)」** 與 **「實盤交易 (Live)」** 兩種模式，其生命週期如下：

### 1. 委託下單 (Order Placement)
*   **模擬模式**：僅在系統資料庫建立 `PENDING` 紀錄，顯示「委託買入中」。
*   **實盤模式**：同步發送 API 請求至永豐金 (Shioaji) 或 MAX 交易所，取得真實委託代碼。

### 2. 成交轉換 (Confirmation & Matching)
由後端 **Matching Engine** 每 30 秒自動偵測：
*   **模擬撮合**：對比第三方即時市價 (Yahoo/Binance)。若 `現價 <= 買入價` (或 `現價 >= 賣出價`)，判定成交並轉為 **Position (持倉)**。在此之前，委託會待在 **「當前持倉」的委託清單** 中。
*   **實盤撮合**：透過券商 API 輪詢委託狀態。當回報為 `Filled (已成交)` 時，更新為正式持倉。

### 3. 結案與損益計算 (History & PnL)
*   **結案歸檔**：賣單成交後，系統自動將標的移除持倉清單，並轉入 **History (歷史)** 清單。
*   **績效計算**：
    *   **實現損益**：`(賣出成交價 - 買入成本) * 數量`。
    *   **獲利率 %**：`((賣出成交價 - 買入成本) / 買入成本) * 100%`。
    *   實盤交易會額外透過定期對帳服務 (Reconciliation) 修正真實的手續費與稅金支出。

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
