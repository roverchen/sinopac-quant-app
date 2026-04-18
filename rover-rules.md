# Rover's Development Rules & Architecture

這份文件記錄了 Sinopac Quant Pro 專案的核心開發準則、架構規範與維運習慣。

## 1. 版本控制與文件規範 (Versioning & Documentation)
- **語意化版本 (Semantic Versioning)**：嚴格遵循 `vX.Y.Z` 格式。核心版本號定義於 `api/main.py`。
- **變更紀錄 (REVISIONS.md)**：
    - 任何功能更新或 Bug Fix 必須同步更新 `REVISIONS.md`。
    - 筆記應包含分類標籤：`[Backend]`、`[Frontend]`、`[Maintenance]`。
- **同步更新**：發布新版本前，確保 `README.md` 中的核心技術描述與最新引擎版本一致。
    - `README.md` 顯示版本需與 `api/main.py` 相同。
    - 若本地啟動 port、部署方式、排程行為或績效口徑有變更，需同步更新文件。

## 2. 後端開發架構 (Backend Architecture)
- **FastAPI / Python 3.11**：
    - **Service-Oriented**：業務邏輯應封裝於 `api/services/` (如 `quant_service.py`)。Route 層僅負責解析請求與調用 Service。
    - **Pydantic Schemas**：統一在 `api/models/schemas.py` 定義資料模型，確保 API 層的類型安全。
    - **資料清洗 (Sanitization)**：返回 JSON 前，務必使用 `sanitize()` helper 處理 `NaN` 或 `Inf` 數值，防止前端解析失效。
- **時區鎖定**：系統全局強制鎖定 `Asia/Taipei` (UTC+8)，確保排程與 K 線分析時間戳的一致性。
- **跨市場金額一致性**：
    - US / Crypto 的模擬成交與損益計算必須先換算為 TWD，再和成本或績效指標比較。
    - 匯率換算應使用快取機制，避免過度請求外部報價源。
- **定期定額模式 (SIP)**：
    - 系統帳戶自動交易以 `sip_amount_twd` 作為單次投入金額基準，預設為 `10,000 TWD`。
    - 台股允許零股，美股使用整股，加密貨幣依市場精度處理數量。

## 3. 前端 UI/UX 準則 (Frontend Guidelines)
- **視覺一致性**：
    - **配色系統**：看漲/買入使用 `#10b981` (Green)，看跌/賣出使用 `#f43f5e` (Red)。
    - **互動反饋**：使用 `Framer Motion` 製作平滑轉換與微動畫；使用 `Lucide React` 作為標準圖標庫。
- **設計哲學**：
    - **RWD 優先**：確保所有 Dashboard 與交易介面在手機端也能流暢操作。
    - **策略拉動條**：左側代表「價值防禦 (Value)」，右側代表「強勢拉回 (Growth/Pullback)」。
- **系統帳戶視角**：
    - `system_auto` 為獨立系統帳戶，需可從 Dashboard deep-link 進入查看。
    - 檢視 `system_auto` 時，手動賣出與撤單操作必須保持禁用。

## 4. 量化邏輯與引擎規範 (Quant Engine Logic)
- **混合數據策略 (Hybrid Data Strategy)**：
    - **Yahoo Finance**：作為日線、MA、MACD 以及相對位階的歷史數據主鏈。
    - **Broker APIs**：實盤行情與下單則切換至 Shioaji (台美股) 或 MAX (加密貨幣)。
- **安全防護 (Safety Guards)**：
    - **流動性過濾**：台股成交值需 > 10M，加密貨幣 > 1M，避免流動性風險。
    - **ATR 波動懲罰**：近期波動率過高 (ATR5 > 1.5x ATR) 應自動減分。
    - **硬停損機制**：跌破月線 3% 或 MACD 動能急轉直下時，評分應立即扣除。
- **相對強度 (RS)**：所有選股評分都應包含與大盤 (^TWII, ^GSPC, BTC) 的相對表現對照。
- **績效計算口徑**：
    - Dashboard 與系統摘要應以 `Total PnL / Total Invested Capital` 作為主要 ROI 指標，避免模擬資金池稀釋報酬率。
- **部位管理**：
    - 模擬與實盤皆以「合併均價 (Average Cost Basis)」作為主要部位管理模型。

## 5. 部署與維運模式 (Deployment & DevOps)
- **分散式鎖 (Distributed Lock)**：每日自動交易任務（TW 14:10 等）需透過 Firestore 的原子鎖機制，確保在 Cloud Run 高併發環境下僅執行一次。
- **模擬 vs 實盤 (Simulation vs Live)**：
    - **模擬模式**：採 `Direct-Fill` (即時成交) 模式，跳過 `PENDING` 狀態以便於快速回測。
    - **實盤模式**：嚴格追蹤委託成交狀態 (Filled)，並支援「合併均價 (Average Cost Basis)」部位管理。
- **排程與喚醒機制**：
    - 程式內部排程時間為 US `06:10`、TW `14:10`、Crypto `23:15`（台北時間）。
    - Cloud Scheduler 應透過 `/api/diag/wakeup` 於外部喚醒服務，驅動補單與補掃描邏輯。
    - 若排程時間有延後（如 `06:15` / `14:15` / `23:20`），應由 `ensure_fresh_scans()` 負責補跑應執行的市場任務。
- **部署習慣**：
    - 主要部署目標為 Google Cloud Run。
    - 實際部署可由 Cloud Build trigger 對 GitHub `main` push 自動觸發，不必假設每次都手動執行 `gcloud builds submit`。
