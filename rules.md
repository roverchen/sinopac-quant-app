# Project Development Rules & Habits

This document codifies the established development patterns and best practices for the Sinopac Quant Pro project.

## 1. Versioning & Documentation
- **Semantic Versioning**: Always bump the `version` in `api/main.py` for every feature update or bug fix.
- **Revision History**: Every release must be documented in `REVISIONS.md` with a summary of changes.
- **README Synchronization**: Key features (like new quant indicators) should be reflected in `README.md` to keep documentation current.

## 2. Coding Standards (Backend)
- **Modular Services**: Logic should reside in `api/services/` (e.g., `quant_service.py`, `auto_trade_service.py`).
- **Schema Integrity**: Always update Pydantic models in `api/models/schemas.py` when adding new data fields to ensure API consistency.
- **Sanitization**: Use the `sanitize()` helper in `quant_service.py` to handle `NaN` or `Inf` values before returning JSON to the frontend.

## 3. UI/UX Principles (Frontend)
- **Visual Consistency**:
  - **Colors**: Use `#10b981` (Green) for Bullish/Buy actions and `#f43f5e` (Red) for Bearish/Sell actions.
  - **Sliders**: "Left" represents Defensive/Value strategies; "Right" represents Aggressive/Growth/Pullback strategies.
- **Interactivity**: Use `Framer Motion` for smooth transitions and `Lucide React` for professional iconography.
- **Deep-Linking**: Ensure important dashboard metrics link directly to their corresponding detailed views with pre-selected filters.

## 4. Quant Engine Logic
- **Relative Strength (RS)**: Always compare stock performance against the relevant market index (^TWII, ^GSPC, BTC) to calculate the RS score.
- **Volume Archetypes**: Maintain and utilize identified volume patterns:
  - *Choking*: Low level + extreme volume shrink.
  - *Bottoming*: Long lower shadow + volume swell.
  - *Washout*: Contraction during pullback.
  - *Momentum Chase*: Gap Up > 7% from bottom levels.

## 5. Deployment Workflow
- **GitHub Triggers**: Use Git Tags (`vX.Y.Z`) to trigger production deployments.
- **Cloud Run**: The primary deployment target is Google Cloud Run via `gcloud builds submit`.
- **Atomic Operations**: Ensure critical tasks like `Auto-Trade` use distributed locks (via GCS) to prevent duplicate execution in containerized environments.

## 6. Interaction Habits
- **Task Tracking**: Maintenance of `task.md`, `implementation_plan.md`, and `walkthrough.md` for major updates.
- **Proactive Verification**: Always check the `/health` endpoint or specific API routes after a deployment to ensure the live environment matches the local codebase.
