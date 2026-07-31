STRATEGY_ACCOUNTS = {
    "system_auto": {
        "user_id": "system_auto",
        "strategy_key": "rover",
        "label": "Rover Rules",
        "short_label": "Rover",
        "markets": ["TW", "US", "CRYPTO"],
        "mirror_followers": True,
        "send_notifications": True,
    },
    "system_eric": {
        "user_id": "system_eric",
        "strategy_key": "eric",
        "label": "Eric Rules",
        "short_label": "Eric",
        "markets": ["TW"],
        "mirror_followers": False,
        "send_notifications": False,
    },
}

# [v2.8.0] Per-market risk parameters. The three markets have fundamentally
# different volatility / crash profiles, so TP/SL/position sizing are separated:
#   - TW:    lowest win rate, strict SL to cap slippage
#   - US:    strongest performer, wider SL allowed, TP raised to let winners run
#   - CRYPTO: crash-prone -> hard stop handled separately; half-size positions
#             and a wider normal SL to avoid noise, larger TP to catch runs.
MARKET_PARAMS = {
    "TW": {"tp_pct": 20.0, "sl_pct": -5.0, "sip_multiplier": 1.0},
    "US": {"tp_pct": 25.0, "sl_pct": -7.0, "sip_multiplier": 1.0},
    "CRYPTO": {"tp_pct": 30.0, "sl_pct": -10.0, "sip_multiplier": 0.5},
}


def get_market_params(market_type: str):
    return MARKET_PARAMS.get(market_type, MARKET_PARAMS["TW"])


def list_strategy_accounts():
    return list(STRATEGY_ACCOUNTS.values())


def list_strategy_account_ids():
    return list(STRATEGY_ACCOUNTS.keys())


def get_strategy_account(user_id: str):
    return STRATEGY_ACCOUNTS.get(user_id)


def is_system_strategy_account(user_id: str) -> bool:
    return user_id in STRATEGY_ACCOUNTS


def supports_market(user_id: str, market_type: str) -> bool:
    cfg = get_strategy_account(user_id)
    return bool(cfg and market_type in cfg.get("markets", []))
