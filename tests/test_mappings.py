# tests/test_mappings.py
from cb2bc.mappings import get_default_mappings, get_account_for_transaction

def test_default_mappings_exist():
    """Default mappings exist for common transaction types"""
    mappings = get_default_mappings()
    assert "buy" in mappings
    assert "sell" in mappings
    assert "send" in mappings
    assert "receive" in mappings
    assert "staking_reward" in mappings

def test_get_account_for_staking():
    """Staking transactions map to Income:Staking"""
    config = {"default_accounts": {"staking_income": "Income:Staking"}}
    account = get_account_for_transaction("staking_reward", "staking", config)
    assert account == "Income:Staking"

def test_get_account_for_fees():
    """Fee transactions map to Expenses:Fees"""
    config = {"default_accounts": {"fees": "Expenses:Fees:Coinbase"}}
    account = get_account_for_transaction("pro_fee", "fee", config)
    assert account == "Expenses:Fees:Coinbase"
