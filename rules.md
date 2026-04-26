# Project Development Rules & Habits

This document codifies the established development patterns and best practices for the Sinopac Quant Pro project.

## 1. Versioning & Documentation
- **Semantic Versioning**: Always bump the `version` in `api/main.py` for every feature update or bug fix.
- **Revision History**: Every release must be documented in `REVISIONS.md` before deployment.
- **README Synchronization**: Key technical features must be reflected in `README.md` to ensure the public-facing documentation matches the latest engine version.
  - Keep the displayed README version aligned with `api/main.py`.
  - Update startup instructions whenever ports, scripts, or local environment assumptions change.
  - Document any user-visible behavior change such as new strategy modes, account restrictions, or performance metric changes.
- **Invested Capital ROI**: For simulation performance, always use `(Total PnL / Total Invested Capital)` as the primary metric to avoid balance dilution.

## 2. Coding Standards (Backend)
- **Modular Services**: Logic should reside in `api/services/` (e.g., `quant_service.py`, `auto_trade_service.py`).
- **Schema Integrity**: Always update Pydantic models in `api/models/schemas.py` when adding new data fields to ensure API consistency.
- **Sanitization**: Use the `sanitize()` helper in `quant_service.py` to handle `NaN` or `Inf` values before returning JSON to the frontend.
- **Cross-Market Currency Safety**: For US and Crypto simulation flows, convert prices and PnL into TWD before comparing against stored cost basis or reporting ROI.
- **SIP Position Sizing**: Auto-trade sizing should be based on `sip_amount_twd` rather than hardcoded share counts.
  - TW supports odd-lot sizing.
  - US uses integer shares.
  - Crypto uses market-appropriate decimal precision.

## 3. UI/UX Principles (Frontend)
- **Visual Consistency**:
  - **Colors**: Use `#10b981` (Green) for Bullish/Buy actions and `#f43f5e` (Red) for Bearish/Sell actions.
  - **Sliders**: "Left" represents Defensive/Value strategies; "Right" represents Aggressive/Growth/Pullback strategies.
- **Interactivity**: Use `Framer Motion` for smooth transitions and `Lucide React` for professional iconography.
- **Deep-Linking**: Ensure important dashboard metrics link directly to their corresponding detailed views with pre-selected filters.
- **System Account Safety**:
  - `system_auto` is a distinct system-managed account.
  - Manual sell and cancel actions must remain disabled when viewing `system_auto`.
  - Dashboard and trading views should preserve deep-links into the system account context.

## 4. Quant Engine Logic
- **Relative Strength (RS)**: Always compare stock performance against the relevant market index (^TWII, ^GSPC, BTC) to calculate the RS score.
- **Volume Archetypes**: Maintain and utilize identified volume patterns:
  - *Choking*: Low level + extreme volume shrink.
  - *Bottoming*: Long lower shadow + volume swell.
  - *Washout*: Contraction during pullback.
  - *Momentum Chase*: Gap Up > 7% from bottom levels.
- **Liquidity & Safety Guards**:
  - *Liquidity Filter*: Minimum daily turnover (TW > 10M, Crypto > 1M) to prevent "Flash Crashes".
  - *Price Guard*: Maximum 3% divergence allowed between scan price and execution price.
  - *Data Bug Shield*: [v2.7.2] Prevent automated "Panic Selling" by skipping exits if ROI is suspiciously low (>-90%), which usually indicates a currency or API data mismatch.
  - *High-Frequency Monitoring*: Maintenance of 5-minute exit checks for automated strategies.
- **Scanning Scope & Robustness**:
  - *Target Coverage*: Total ~6,000 stocks (TW: Listed/OTC/Emerging/ETF, US: S&P500/NASDAQ, Crypto: MAX).
  - *Hybrid Strategy*: Use dynamic scrapers for fresh names, but always maintain a large JSON-based backup list (>500 core stocks) to handle cloud environment SSL/404 failures.
  - *Incremental Updates*: For massive lists (>5,000), implement partial saves every 100-500 stocks to ensure progress is persisted even if the task is throttled or killed.

## 5. Deployment Workflow
- **GitHub Triggers & Tagging**: 
  - Use Git Tags in `vX.Y.Z` format to trigger automated CI/CD or staging deployments.
  - **Sequence**: Always commit `README.md` and `REVISIONS.md` *before* pushing the final Version Tag.
  - **Re-tagging**: If documentation needs fixing post-commit, delete the remote tag and re-push it to ensure the build contains correct metadata.
- **Cloud Run**: The primary deployment target is Google Cloud Run via `gcloud builds submit`.
- **Atomic Operations**: Ensure critical tasks like `Auto-Trade` use distributed locks (via Firestore) to prevent duplicate execution in containerized environments.
- **Local Environment Consistency**: Keep `run_local.sh`, virtualenv usage, and dependency assumptions aligned with `requirements.txt` and README instructions.

## 6. Interaction Habits
- **Task Tracking**: For major updates, leave a durable change trail in project artifacts that actually exist in the repo, such as `REVISIONS.md`, implementation notes, or PR descriptions. Do not rely on undocumented placeholder files.
- **Proactive Verification**: Always check the `/health` endpoint or specific API routes after a deployment to ensure the live environment matches the local codebase.
