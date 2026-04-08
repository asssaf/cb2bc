from cb2bc.converter import collect_accounts, convert_transaction


def test_convert_usdc_buy_no_conversion_account():
    """Verify USDC buy uses bank account, not Conversion account"""
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "transfers": "Equity:Transfers",
        },
    }

    # Buy USDC with USD
    txn = {
        "id": "txn-usdc",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "100.00", "currency": "USDC"},
        "native_amount": {"amount": "100.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Bought USDC",
    }

    result = convert_transaction([txn], config)

    assert "Assets:Coinbase:USDC" in result
    assert "100.00 USDC @ 1.00 USD" in result
    assert "Assets:Bank:Checking" in result
    assert "Assets:Coinbase:Conversion" not in result


def test_convert_usd_sell_no_conversion_account():
    """Verify USDC sell uses bank account, not Conversion account"""
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
        },
    }

    # Sell USDC for USD
    txn = {
        "id": "txn-usdc-sell",
        "type": "sell",
        "status": "completed",
        "amount": {"amount": "-50.00", "currency": "USDC"},
        "native_amount": {"amount": "50.00", "currency": "USD"},
        "created_at": "2024-01-15T11:30:00Z",
        "description": "Sold USDC",
    }

    result = convert_transaction([txn], config)

    assert "Assets:Coinbase:USDC" in result
    assert "-50.00 USDC @ 1.00 USD" in result
    assert "Assets:Bank:Checking" in result
    assert "Assets:Coinbase:Conversion" not in result


def test_collect_accounts_no_conversion_account():
    """Verify collect_accounts doesn't include the Conversion account for USD/USDC"""
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
        },
    }

    txn = {
        "id": "txn-usdc",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "100.00", "currency": "USDC"},
        "native_amount": {"amount": "100.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Bought USDC",
    }

    accounts = collect_accounts([txn], config)
    assert "Assets:Coinbase:USDC" in accounts
    assert "Assets:Bank:Checking" in accounts
    assert "Assets:Coinbase:Conversion" not in accounts
