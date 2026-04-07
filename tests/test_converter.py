# tests/test_converter.py
from cb2bc.converter import convert_transaction, format_commodity


def test_format_commodity():
    """Generate beancount commodity declaration"""
    result = format_commodity("BTC")
    assert result == "1970-01-01 commodity BTC"


def test_convert_buy_transaction():
    """Convert buy transaction to beancount format"""
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {"bank_checking": "Assets:Bank:Checking"},
    }

    txn = {
        "id": "txn-123",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "0.001", "currency": "BTC"},
        "native_amount": {"amount": "50.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Bought BTC",
    }

    result = convert_transaction(txn, config)

    assert '2024-01-15 * "Bought BTC" ^coinbase-txn-123' in result
    assert "Assets:Coinbase:BTC" in result
    assert "0.001 BTC @@ 50.00 USD" in result
    assert "Assets:Bank:Checking  -50.00 USD" in result


def test_convert_staking_reward():
    """Convert staking reward to income"""
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {"staking_income": "Income:Staking"},
    }

    txn = {
        "id": "txn-456",
        "type": "staking_reward",
        "status": "completed",
        "amount": {"amount": "0.05", "currency": "ETH"},
        "created_at": "2024-02-01T00:00:00Z",
        "description": "ETH2 staking reward",
    }

    result = convert_transaction(txn, config)

    assert "2024-02-01" in result
    assert "Assets:Coinbase:ETH" in result
    assert "Income:Staking" in result


def test_convert_send():
    """Convert send transaction"""
    config = {"account_prefix": "Assets:Coinbase"}

    txn = {
        "id": "txn-789",
        "type": "send",
        "status": "completed",
        "amount": {"amount": "-0.1", "currency": "BTC"},
        "created_at": "2024-03-01T12:00:00Z",
        "description": "Sent to external wallet",
    }

    result = convert_transaction(txn, config)

    assert "2024-03-01" in result
    assert "Assets:Coinbase:BTC" in result
    assert "-0.1 BTC" in result
    assert "Equity:Transfers" in result
