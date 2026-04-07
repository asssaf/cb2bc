from cb2bc.converter import convert_transaction


def test_merged_transactions():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Two transactions representing two sides of the same buy
    txn_btc = {
        "id": "txn-btc-123",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "0.001", "currency": "BTC"},
        "native_amount": {"amount": "50.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Bought BTC",
        "buy": {
            "id": "shared-buy-id",
            "total": {"amount": "51.00", "currency": "USD"},
            "subtotal": {"amount": "50.00", "currency": "USD"},
            "fee": {"amount": "1.00", "currency": "USD"},
        },
    }

    txn_usd = {
        "id": "txn-usd-456",
        "type": "sell",
        "status": "completed",
        "amount": {"amount": "-51.00", "currency": "USD"},
        "native_amount": {"amount": "-51.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Paid for BTC",
        "sell": {
            "id": "shared-buy-id",
            "total": {"amount": "51.00", "currency": "USD"},
            "subtotal": {"amount": "50.00", "currency": "USD"},
            "fee": {"amount": "1.00", "currency": "USD"},
        },
    }

    result = convert_transaction([txn_btc, txn_usd], config)

    assert '2024-01-15 * "Bought BTC / Paid for BTC" ^coinbase-shared-buy-id' in result
    assert 'coinbase_id: "txn-btc-123 txn-usd-456"' in result
    assert 'coinbase_trade_id: "shared-buy-id"' in result
    assert "Assets:Coinbase:BTC  0.001 BTC @@ 50.00 USD" in result
    assert "Assets:Coinbase:USD  -51.00 USD" in result
    assert "Expenses:Fees:Coinbase  1.00 USD" in result
    # It is balanced, so no Bank:Checking leg
    assert "Assets:Bank:Checking" not in result


def test_crypto_to_crypto_merged():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    txn_eth_sell = {
        "id": "txn-eth-sell",
        "type": "sell",
        "status": "completed",
        "amount": {"amount": "-1.0", "currency": "ETH"},
        "native_amount": {"amount": "-3000.00", "currency": "USD"},
        "created_at": "2024-01-17T10:30:00Z",
        "description": "Sold ETH for BTC",
        "sell": {
            "id": "shared-trade-id",
            "total": {"amount": "3000.00", "currency": "USD"},
            "subtotal": {"amount": "2990.00", "currency": "USD"},
            "fee": {"amount": "10.00", "currency": "USD"},
        },
    }

    txn_btc_buy = {
        "id": "txn-btc-buy",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "0.06", "currency": "BTC"},
        "native_amount": {"amount": "3000.00", "currency": "USD"},
        "created_at": "2024-01-17T10:30:00Z",
        "description": "Bought BTC with ETH",
        "buy": {
            "id": "shared-trade-id",
            "total": {"amount": "3000.00", "currency": "USD"},
            "subtotal": {"amount": "2990.00", "currency": "USD"},
            "fee": {"amount": "10.00", "currency": "USD"},
        },
    }

    result = convert_transaction([txn_eth_sell, txn_btc_buy], config)

    assert (
        '2024-01-17 * "Sold ETH for BTC / Bought BTC with ETH" '
        "^coinbase-shared-trade-id" in result
    )
    assert "Assets:Coinbase:ETH  -1.0 ETH @@ 2990.00 USD" in result
    assert "Assets:Coinbase:BTC  0.06 BTC @@ 2990.00 USD" in result
    assert "Expenses:Fees:Coinbase  10.00 USD" in result
    # We have fees, so we need a balancing leg
    assert "Expenses:Fees:Coinbase" in result


def test_usdc_formatting():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {"transfers": "Equity:Transfers"},
    }

    txn = {
        "id": "txn-usdc-123",
        "type": "send",
        "status": "completed",
        "amount": {"amount": "100.00", "currency": "USDC"},
        "native_amount": {"amount": "100.00", "currency": "USD"},
        "created_at": "2024-01-15T10:30:00Z",
        "description": "Sent USDC",
    }

    result = convert_transaction(txn, config)

    assert "Assets:Coinbase:USDC  100.00 USDC @ 1.00 USD" in result
    assert "Equity:Transfers" in result


def test_user_scenario_trade():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Scenario from user: DOT bought with USDC
    txn_dot = {
        "id": "71092890-329d-11f1-ae1e-00163e258bd",
        "type": "buy",
        "status": "completed",
        "amount": {"amount": "84.744659372", "currency": "DOT"},
        "native_amount": {"amount": "978.76", "currency": "USD"},
        "created_at": "2020-08-12T21:18:10Z",
        "description": "Trade",
        "buy": {"id": "6dea8ee2-329d-11f1-89dc-00163e258bd"},
    }

    txn_usdc = {
        "id": "72344452-329d-11f1-9797-00163e258bda",
        "type": "sell",
        "status": "completed",
        "amount": {"amount": "-1000", "currency": "USDC"},
        "native_amount": {"amount": "-1000.00", "currency": "USD"},
        "created_at": "2020-08-12T21:18:10Z",
        "description": "Trade",
        "sell": {"id": "6dea8ee2-329d-11f1-89dc-00163e258bd"},
    }

    result = convert_transaction([txn_dot, txn_usdc], config)

    # Check concatenated IDs
    assert (
        'coinbase_id: "71092890-329d-11f1-ae1e-00163e258bd '
        '72344452-329d-11f1-9797-00163e258bda"' in result
    )
    # Check trade_id
    assert 'coinbase_trade_id: "6dea8ee2-329d-11f1-89dc-00163e258bd"' in result
    # Check USDC formatting
    assert "Assets:Coinbase:USDC  -1000 USDC @ 1.00 USD" in result
    # Check DOT formatting
    assert "Assets:Coinbase:DOT  84.744659372 DOT @@ 978.76 USD" in result
    # Check balancing leg is categorized as fee
    assert "Expenses:Fees:Coinbase  21.24 USD" in result
