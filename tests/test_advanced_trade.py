from cb2bc.converter import convert_transaction, generate_declarations


def test_advanced_trade_fill_merging():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Example from user
    txn_quote = {
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

    txn_base = {
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

    result = convert_transaction([txn_quote, txn_base], config)

    order_id = "00a6d4e2-76bf-431e-9a93-08d3315dff66"
    assert f'2023-01-12 * "Advanced Trade Fill" ^coinbase-{order_id}' in result
    assert f'coinbase_trade_id: "{order_id}"' in result

    # Check legs
    assert "Assets:Coinbase:USDC  12269.800000 USDC @ 1.00 USD" in result or (
        "Assets:Coinbase:USDC  12269.8 USDC @ 1.00 USD" in result
    )
    assert "Assets:Coinbase:BTC  -0.100000 BTC @ 122698.000000 USD" in result or (
        "Assets:Coinbase:BTC  -0.1 BTC @ 122698 USD" in result
    )

    # Check commission
    assert "Expenses:Fees:Coinbase  49.0792 USD" in result
    assert "Assets:Coinbase:USD  -49.0792 USD" in result


def test_multiple_fills():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Two fills for the same order
    order_id = "multiple-fills-id"

    # Fill 1
    f1_q = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:10Z",
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": order_id,
        },
        "amount": {"amount": "100", "currency": "USD"},
        "id": "f1q",
    }
    f1_b = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:10Z",
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": order_id,
        },
        "amount": {"amount": "0.002", "currency": "BTC"},
        "id": "f1b",
    }

    # Fill 2
    f2_q = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:15Z",
        "advanced_trade_fill": {
            "commission": "2.0",
            "fill_price": "60000",
            "order_id": order_id,
        },
        "amount": {"amount": "120", "currency": "USD"},
        "id": "f2q",
    }
    f2_b = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:15Z",
        "advanced_trade_fill": {
            "commission": "2.0",
            "fill_price": "60000",
            "order_id": order_id,
        },
        "amount": {"amount": "0.002", "currency": "BTC"},
        "id": "f2b",
    }

    result = convert_transaction([f1_q, f1_b, f2_q, f2_b], config)

    # Should have 2 fee postings and 2 balancing asset postings
    assert "Expenses:Fees:Coinbase  1.0 USD" in result
    assert "Assets:Coinbase:USD  -1.0 USD" in result
    assert "Expenses:Fees:Coinbase  2.0 USD" in result
    assert "Assets:Coinbase:USD  -2.0 USD" in result


def test_declarations_include_usd():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "fees": "Expenses:Fees:Coinbase",
        },
    }
    txn = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:10Z",
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": "id",
        },
        "amount": {"amount": "0.002", "currency": "BTC"},
        "id": "id",
    }

    declarations = generate_declarations([txn], config)
    assert "open Assets:Coinbase:USD" in declarations
    assert "open Expenses:Fees:Coinbase" in declarations
