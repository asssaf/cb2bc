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
    assert 'coinbase_id: "txn-btc-123"' in result
    assert 'coinbase_id: "txn-usd-456"' in result
    assert 'coinbase_shared_id: "shared-buy-id"' in result
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
    # We have fees, so we need a balancing leg (unless it already balances,
    # but here it does not since ETH/BTC legs use the same 2990 USD total price).
    assert "Assets:Bank:Checking" in result
