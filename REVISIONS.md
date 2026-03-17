# Sinopac Quant Pro - Revision History

This document tracks all version changes and feature updates for the Sinopac Quant Pro system.

## Version 2.1 Series

### v2.1.71 (2026-03-17)
- **UI Column Reordering**: Moved the "Mode" (模式/實盤) column to the first position in both the Positions and History tables for better visibility and faster identification of simulation vs. live trades.

### v2.1.70 (2026-03-16)
- **Balance Separation Fix**: Resolved double-counting and incorrect data linkage between Sinopac and MAX balances.
- **Improved USDT Estimate**: Implemented real-time exchange rate fetching for more accurate TWD/USDT asset valuation.
- **Shioaji Decoupling**: Reverted Sinopac balance getter to be independent of MAX credentials.

### v2.1.69 (2026-03-16)
- **MAX Multi-Asset Integration**: Integrated MAX TWD balances into the total account balance.
- **Crypto Position Injection**: Non-zero holdings from MAX (e.g., BTC, DOT) are now automatically injected into the position list.
- **TWD Price Conversion**: Standardized all crypto position prices and PnL to TWD using real-time exchange rates.
- **Enhanced Market Discovery**: Improved synchronization logic to ensure historical trades for coins like DOT are correctly captured and cost-bases calculated.

### v2.1.68 (2026-03-16)
- **UI Robustness & Versioning**: Added visible version number (e.g., v2.1.68) in the header for diagnostic purposes.
- **Timestamp Rendering Fix**: Enhanced Date formatting logic in `TradingControl.jsx` to handle missing or `None` values gracefully.
- **Cache Invalidation**: Rebuilt and redeployed static frontend bundle to ensure latest changes are served.

### v2.1.67 (2026-03-16)
- **Error Message Parsing**: Fixed `Status.Failed ()` error by extracting detailed rejection reasons from Shioaji API payload.
- **Enhanced Visibility**: Backend now surfaces specific reasons like "Account Not Acceptable" or "Balance Insufficient" to the frontend.

### v2.1.66 (2026-03-16)
- **Legacy Position Fallback**: Implemented logic to derive timestamps from legacy position IDs (e.g., POS-XXXXXXXX) when explicit buy records don't exist.
- **UI Improvement**: Prevents "系統升級前" from showing for older positions.

### v2.1.65 (2026-03-16)
- **Sell Dialog Timestamp Enhancement**: Added "買入委託時間" and "買入確認時間" to the sell modal.
- **Backend Data Sync**: Updated `shioaji_service.py` and `reconciliation_service.py` to track distinct order and fill timings.

### v2.1.64 (2026-03-16)
- **Crypto TWD-Centric Pricing**: Automatically fetches USD/TWD rates and converts all crypto list prices to TWD.
- **Auto-Trade Execution**: Manually triggered a crypto scan and automated order placement (DOT/TWD) on MAX.

### v2.1.63 (2026-03-16)
- **Hybrid Data Scanner**: Implemented "USD Analysis + TWD Trading" model for crypto scanning.
- **Market Scan Recovery**: Completed full crypto market scan and updated core sélection pools.

### v2.1.62 (2026-03-16)
- **Crypto Module Refactor**: Standardized all crypto operations to TWD-based pairs by default.
- **Dashboard Synchronization**: Integrated BTC-TWD as the default crypto index on the trend chart.

### v2.1.61 (2026-03-16)
- **MAX TWD Priority**: Preliminary implementation of TWD-preference logic for MAX trading pairs.

### v2.1.60 (2026-03-16)
- **Real-time Trend Chart**: Connected dashboard trend analysis to real APIs (Taiwan Index, S&P 500, BTC).
- **Core Selection Integration**: Visualizes performance of Top 5 scored stocks against market benchmarks.

### v2.1.59 (2026-03-16)
- **Order Placement Fix**: Resolved symbol formatting errors for crypto orders (removing prefixes and correcting suffixes).

### v2.1.58 (2026-03-16)
- **MAX Market Discovery**: Implemented automatic pair recognition in reconciliation to ensure all markets (e.g., DOT) are synced correctly.

### v2.1.57 (2026-03-16)
- **UI Experience**: Added loading progress bars when fetching detailed historical data for stock cards.

### v2.1.56 (2026-03-16)
- **Watchlist Stability**: Fixed `AttributeError` when sorting items from Firestore cache.

### v2.1.55 (2026-03-16)
- **UI Cleanup**: Removed unnecessary robot status bars and manual triggers from the main trading control.

### v2.1.53 (2026-03-16)
- **Watchlist Recovery**: Fixed filtering logic to ensure symbols like `BTC-USD` and `2330` are correctly categorized and displayed.
- **Crypto Deduplication**: Optimized MAX API grabbing to ensure unique trading pairs (prioritizing USDT).

### v2.1.50 (2026-03-16)
- **Syntax Recovery**: Fixed syntax errors in `diag.py` and patched `api/main.py`.
- **System Stability**: Standardized internal error handling for various data formats.

### v2.1.45 - v2.1.48 (2026-03-16)
- **Symbol Refactoring**: Shifted internal symbol logic to prioritize MAX format.
- **System Diagnostics**: Fixed SSL Certificate Verification errors on Mac.

### v2.1.43 (2026-03-15)
- **Crypto Migration**: Handled MATIC-to-POL migration and improved DOT sync.

### v2.1.10 - v2.1.24 (2026-03-14 - 2026-03-15)
- **Initial v2.1 Rollout**:
  - Parallel Re-scoring (100x speedup).
  - Mobile responsiveness improvements.
  - Transaction precision and Taiwan stock data robustness enhancements.
  - Unified list interactions and order cancellation support.

---
*End of log. Continued development and refinement ongoing.*
