# Sinopac Quant Pro (Revisions)

## Version 2.1 Series

### v2.2.0 (2026-03-20) - **Quant Engine v2 Upgrade**
- **Enhanced Scoring Core**:
  - [Backend] Implemented **Relative Strength (RS)** comparison vs indices (^TWII, ^GSPC, BTC).
  - [Backend] Added **Volume Behavioral Detection**: Choking Volume (底部窒息量), Bottoming Volume (止跌量), and Washout Volume (縮量回測).
  - [Backend] Added **MACD Histogram Slope** to detect convergence/divergence earlier than crosses.
  - [Backend] Implemented **ATR-Volatility Filter** to penalize sudden volatility spikes (Fake breakouts).
  - [Backend] Added **Hard Stop-Loss Penalty** (Break MA20-3% or MACD negative flip).
  - [Backend] Updated scoring weights to 50/10/20/20 (Value) and 10/50/20/20 (Growth).

### v2.1.94 (2026-03-20)
- **UI Cleanup & Optimization**:
  - [Frontend] Relocated `sub_orders` (history of buys) from the "Current Positions" table to the "Sell Modal".
  - [Frontend] Improved Sell Modal layout with a scrollable history section for multiple buy entries.
  - [Frontend] Fixed JSX structural errors in `TradingControl.jsx`.

### v2.1.93 (2026-03-20)
- **Dashboard Performance Boost**:
  - [Backend] Added 1-hour in-memory cache for `/trend` API to avoid slow Yahoo Finance fetches.
  - [Backend] Optimized `/results` to skip expensive O(N log N) sorting when `defense_weight` is None.
  - [Frontend] Parallelized market highlight fetching (TW/US/Crypto) in `Dashboard.jsx`.

### v2.1.92 (2026-03-20)
- **Fast Re-score & Caching**: 
  - [Backend] Optimized `/analyze` and `/results` to re-score using sub-scores without K-line dependency.
  - [Frontend] Fixed "My List" cache key to include weights, preventing stale results.
- **UI Unification**:
  - [Frontend] Unified all strategy sliders: Left=Value, Right=Pullback.
  - [Frontend] Added strategy weight slider to "Strategy Scan" page.
- **Mirror Trading Fixes**:
  - [Backend] Normalized strategy weight scaling (0.5 ratio = 100% budget).
  - [Backend] Added $1,000,000 default balance for simulation/mock accounts.

### v2.1.89 (2026-03-19)
- **Distributed Auto-Trade Lock**: 
    - **Concurrency Fix**: Implemented an atomic distributed lock via Firestore (`acquire_daily_trade_lock`) to guarantee that only ONE Cloud Run instance can execute the daily auto-trade. This prevents duplicated multi-buys (e.g. buying 3 times at once) caused by Cloud Run auto-scaling multiple in-memory scheduler threads at the exact same minute.

### v2.1.87 (2026-03-19)
- **Sub-Order History Tracking**:
    - **Averaging Audit**: Modified the backend matching engine (`trade_engine.py`) to preserve individual batch purchase details (`qty`, `buy_price`, `time`) inside a `sub_orders` array when merging into an average-cost Position.
    - **Hover UI Details**: Upgraded the `TradingControl.jsx` frontend to feature a hidden dropdown menu under each aggregated stock. Users can now instantly recall the specific dates and prices of multiple sequential additions that constructed their current position without breaking the clean UI.

### v2.1.86 (2026-03-18)
- **Advanced Mirror Trading UI & Logic**:
    - **Strategy Allocation Slider**: Replaced individual strategy weights with a unified single ratio slider (Value vs. Pullback) for more intuitive budget splitting.
    - **Total Allocation Budget**: Introduced a single "Total Allocation" percentage input, which defines the maximum overall account balance to risk per trade.
    - **Auto-Trade Timezone Fix**: Enforced `Asia/Taipei` timezone globally in the backend (`api/main.py`) to guarantee that scheduled tasks (US 06:10, TW 14:10, Crypto 23:15) always trigger at the correct Taiwan local time, regardless of the underlying server's UTC configuration.

### v2.1.85 (2026-03-18)
- **Granular Trade Constraints**:
    - **Score-Based Weights**: Implemented independent handling for Value and Pullback strategy allocations within the core trading engine.
    - **Max Order Limit**: Added an absolute TWD cap setting per order, ensuring that even under high percentage allocations, the executed trade value is strictly capped.
    - **Safety Confirmation**: Added a mandatory high-contrast confirmation modal requiring users to explicitely click to enable live mirror trading, preventing accidental test-mode toggles.

### v2.1.82 (2026-03-18)
- **Notification System**:
    - **Email Notifications**: Integrated SMTP service to send automated trade notifications after daily auto-trade execution or TP/SL triggers.
    - **Preference Toggle**: Added a "Notification Settings" section in the System Settings page, allowing users to opt-in or out of daily trade emails.
    - **Backend Infrastructure**: Added user settings storage in Firestore and new API endpoints for preference management.

### v2.1.81 (2026-03-18)
- **UI Consistency Pass**:
    - **History Alignment**: Redesigned the "Trade History" table to match the layout and styling of the "Current Positions" table. This includes unified column headers, large/small font patterns for symbols/names, and consistent status badges.

### v2.1.80 (2026-03-18)
- **Settings Page Enhancement**:
    - **Relocated Assets**: Moved Sinopac and MAX balance cards from the Dashboard to the Settings page. This provides a cleaner dashboard view while placing account balances directly where API credentials are managed.

### v2.1.79 (2026-03-18)
- **Trade History Sorting & Precision**:
    - **Backend Sorting**: Implemented descending timestamp sorting for `/history` and `/pending` API endpoints.
    - **Timestamp Precision**: Updated the frontend to display both date and time (HH:MM) for trade history entries, improving tracking accuracy.

### v2.1.78 (2026-03-18)
- **Auto-Trade Robustness Upgrade**:
    - **Cross-Day Makeup Logic**: Refactored `ensure_fresh_scans` to support compensatory trades across different days, ensuring missed windows are always addressed.
    - **Cloud Run Optimization**: Resolved issues where Cloud Run's ephemeral nature caused missed scheduled scans by implementing a persistent last-trade timestamp check in Firestore.

### v2.1.75 (2026-03-16)
- **Trading Control UI Refactoring**:
    - **Tabbed Interface**: Removed the complex header block and implemented a clean tabbed interface to switch between "Personal" and "System" accounts.
    - **Performance Metrics**: Integrated ROI and Sync buttons directly into the tab headers for better accessibility.

### v2.1.70 (2026-03-16)
- **Simulated Trading Costs**:
    - **Fee & Tax Engine**: Implemented realistic fee and tax calculations for simulation mode (0.1425% fee, 0.3% tax for TW).
    - **Net P/L Reporting**: Trade history now reflects net realized profit after accounting for all transaction costs.

### v2.1.69 (2026-03-16)
- **MAX Order Synchronization**:
    - **Enhanced Market Discovery**: Improved synchronization logic to ensure historical trades for coins like DOT are correctly captured and cost-bases calculated.

### v2.1.68 (2026-03-16)
- **UI Robustness & Versioning**: Added visible version number in the header for diagnostic purposes.
- **Timestamp Rendering Fix**: Enhanced Date formatting logic in `TradingControl.jsx` to handle missing or `None` values gracefully.
- **Cache Invalidation**: Rebuilt and redeployed static frontend bundle to ensure latest changes are served.
