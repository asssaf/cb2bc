# cb2bc/config.py
from pathlib import Path
from typing import Dict, Any, Optional
import json
import os

DEFAULT_CONFIG = {
    "account_prefix": "Assets:Coinbase",
    "key_name": None,
    "private_key": None,
    "default_accounts": {
        "staking_income": "Income:Staking",
        "fees": "Expenses:Fees:Coinbase",
        "bank_checking": "Assets:Bank:Checking",
    },
    "transaction_mappings": {},
}

def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration from file, env vars, with defaults"""
    config = DEFAULT_CONFIG.copy()

    # Try loading from file
    if config_path and config_path.exists():
        with open(config_path) as f:
            file_config = json.load(f)
            config.update(file_config)

    # Override with environment variables
    if key_name := os.environ.get("COINBASE_KEY_NAME"):
        config["key_name"] = key_name
    if private_key := os.environ.get("COINBASE_PRIVATE_KEY"):
        config["private_key"] = private_key

    return config
