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
