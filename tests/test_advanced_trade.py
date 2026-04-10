from cb2bc.converter import convert_transaction


def test_advanced_trade_fill_merge():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    txn_usdc = {
        "advanced_trade_fill": {
            "commission": "49.0792",
            "fill_price": "122698",
            "order_id": "00a6d4e2-76bf-431e-9a93-08d3315dff66",
            "order_side": "sell",
            "product_id": "BTC-USDC",
        },
        "amount": {"amount": "12269.8", "currency": "USDC"},
        "created_at": "2023-01-12T21:18:10Z",
        "id": "a0ea8093-1068-4230-a8ea-7e6e61f03688",
        "native_amount": {"amount": "12269.80", "currency": "USD"},
        "status": "completed",
        "type": "advanced_trade_fill",
    }

    txn_btc = {
        "advanced_trade_fill": {
            "commission": "49.0792",
            "fill_price": "122698",
            "order_id": "00a6d4e2-76bf-431e-9a93-08d3315dff66",
            "order_side": "sell",
            "product_id": "BTC-USDC",
        },
        "amount": {"amount": "-0.1", "currency": "BTC"},
        "created_at": "2023-01-12T21:18:10Z",
        "id": "39008944-d74b-4735-9781-41794924e6be",
        "native_amount": {"amount": "-12268.53", "currency": "USD"},
        "status": "completed",
        "type": "advanced_trade_fill",
    }

    # In the real CLI, they are grouped before calling convert_transaction
    # But convert_transaction also handles a list.
    result = convert_transaction([txn_usdc, txn_btc], config)

    expected_header = (
        '2023-01-12 * "Advanced Trade Fill" '
        "^coinbase-00a6d4e2-76bf-431e-9a93-08d3315dff66"
    )
    assert expected_header in result
    # Should use the fill_price (122698) with @ USD for base currency leg
    assert "Assets:Coinbase:BTC  -0.1 BTC @ 122698 USD" in result
    # USDC leg should be net of commission: 12269.8 - 49.0792 = 12220.7208
    # and include the valuation
    assert "Assets:Coinbase:USDC  12220.7208 USDC @ 1.00 USD" in result
    assert "Expenses:Fees:Coinbase  49.0792 USD" in result


def test_advanced_trade_fill_buy_merge():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    txn_usdc = {
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": "buy-order-id",
            "order_side": "buy",
            "product_id": "BTC-USDC",
        },
        "amount": {"amount": "-100.0", "currency": "USDC"},
        "created_at": "2024-01-15T10:30:00Z",
        "id": "txn-usdc",
        "status": "completed",
        "type": "advanced_trade_fill",
    }

    txn_btc = {
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": "buy-order-id",
            "order_side": "buy",
            "product_id": "BTC-USDC",
        },
        "amount": {"amount": "0.002", "currency": "BTC"},
        "created_at": "2024-01-15T10:30:00Z",
        "id": "txn-btc",
        "status": "completed",
        "type": "advanced_trade_fill",
    }

    result = convert_transaction([txn_usdc, txn_btc], config)

    assert "Assets:Coinbase:BTC  0.002 BTC @ 50000 USD" in result
    # USDC leg should be net of commission: -100.0 - 1.0 = -101.0
    assert "Assets:Coinbase:USDC  -101.0 USDC @ 1.00 USD" in result
    assert "Expenses:Fees:Coinbase  1.0 USD" in result
