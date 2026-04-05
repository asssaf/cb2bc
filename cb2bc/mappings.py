# cb2bc/mappings.py

DEFAULT_MAPPINGS = {
    # Receives and deposits
    "receive": "transfer",
    "fiat_deposit": "transfer",
    # Sends and withdrawals
    "send": "transfer",
    "fiat_withdrawal": "transfer",
    # Buys and sells
    "buy": "buy",
    "sell": "sell",
    # Trading
    "trade": "trade",
    "advanced_trade_fill": "trade",
    # Staking and rewards
    "staking_reward": "staking",
    "inflation_reward": "staking",
    "learning_reward": "income",
    # Fees
    "pro_fee": "fee",
    "coinbase_fee": "fee",
}


def get_default_mappings() -> dict[str, str]:
    """Return default transaction type mappings"""
    return DEFAULT_MAPPINGS.copy()


def get_account_for_transaction(txn_type: str, category: str, config: dict) -> str:
    """
    Get beancount account name for a transaction type.

    Args:
        txn_type: Coinbase transaction type
        category: Mapped category (buy, sell, transfer, staking, fee, etc.)
        config: Configuration dict with default_accounts

    Returns:
        Beancount account name
    """
    defaults = config.get("default_accounts", {})

    if category == "staking" or category == "income":
        return defaults.get("staking_income", "Income:Staking")
    elif category == "fee":
        return defaults.get("fees", "Expenses:Fees:Coinbase")
    elif category in ("buy", "sell"):
        return defaults.get("bank_checking", "Assets:Bank:Checking")
    else:
        # For transfers, return a balancing account
        return defaults.get("transfers", "Equity:Transfers")
