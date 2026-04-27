# Skill: Simulated Execution Agent (模擬下單執行員)

## 1. 技能概述 (Overview)
此技能負責將「分析建議」轉化為「帳戶部位」。它不只是記錄數據，而是透過交易引擎模擬真實的委託、成交與部位建立流程。這是自動交易系統的最後一哩路。

## 2. 執行流程 (Execution Flow)
*   **預算檢查**：確認 `system_auto` 帳戶有足夠的模擬資金（預設 1,000,000 TWD）。
*   **即時詢價**：調用 `ShioajiService.get_current_price` 獲取標的最新的市場成交價。
*   **委託下單**：
    *   調用 `ShioajiService.place_order` 並開啟 `is_simulation=True` 模式。
    *   使用 `MockShioajiClient` 進行 `Immediate-Fill` (即時成交) 模擬，以跳過掛單等待。
*   **同步與通知**：成交後自動更新 Firestore 的 `trade_logs` 與 `positions` 集合，並觸發 Email 通知。

## 3. 技能特性 (Agent Properties)
*   **安全隔離**：強制限制在 `is_simulation=True` 模式，除非獲取實盤授權。
*   **數據完整性**：自動記錄 `trade_id`、成交時間與手續費估計。

## 4. 執行命令範例 (Execution Command)
> "執行 `Simulated Execution Agent`。針對標的 **3712 (永崴投控)** 建立模擬買入部位。
> 1. 金額：$10,000 TWD。
> 2. 模式：模擬交易 (Simulation)。
> 3. 帳戶：system_auto。"

## 5. 成交預期結果
*   **交易紀錄**：新增一筆 `Buy 3712 @ $22.5 (Qty: 444)` 的紀錄。
*   **庫存狀態**：`system_auto` 的庫存中出現 3712，並開始計算即時 ROI。
