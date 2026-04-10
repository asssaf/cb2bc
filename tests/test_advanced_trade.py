from cb2bc.converter import convert_transaction, generate_declarations


def test_advanced_trade_fill_merging():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "bank_checking": "Assets:Bank:Checking",
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Example from user: BTC-USDC
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
    assert "Assets:Coinbase:USDC  12269.8 USDC @ 1.00 USD" in result
    assert "Assets:Coinbase:BTC  -0.1 BTC @ 122698 USD" in result

    # Check commission
    assert "Expenses:Fees:Coinbase  49.0792 USD" in result
    assert "Assets:Coinbase:USD  -49.0792 USD" in result


def test_advanced_trade_fill_usd():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "fees": "Expenses:Fees:Coinbase",
        },
    }

    # Example with USD instead of USDC
    txn_quote = {
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": "order-usd",
            "product_id": "BTC-USD",
        },
        "amount": {"amount": "100", "currency": "USD"},
        "created_at": "2023-01-12T21:18:10Z",
        "id": "q1",
        "status": "completed",
        "type": "advanced_trade_fill",
    }
    txn_base = {
        "advanced_trade_fill": {
            "commission": "1.0",
            "fill_price": "50000",
            "order_id": "order-usd",
            "product_id": "BTC-USD",
        },
        "amount": {"amount": "-0.002", "currency": "BTC"},
        "created_at": "2023-01-12T21:18:10Z",
        "id": "b1",
        "status": "completed",
        "type": "advanced_trade_fill",
    }

    result = convert_transaction([txn_quote, txn_base], config)

    # USD should NOT have @ 1.00 USD
    assert "Assets:Coinbase:USD  100 USD" in result
    assert "@ 1.00 USD" not in result


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
            "product_id": "BTC-USD",
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
            "product_id": "BTC-USD",
        },
        "amount": {"amount": "-0.002", "currency": "BTC"},
        "id": "f1b",
    }

    # Fill 2 (different price and commission)
    f2_q = {
        "type": "advanced_trade_fill",
        "status": "completed",
        "created_at": "2023-01-12T21:18:15Z",
        "advanced_trade_fill": {
            "commission": "2.0",
            "fill_price": "60000",
            "order_id": order_id,
            "product_id": "BTC-USD",
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
            "product_id": "BTC-USD",
        },
        "amount": {"amount": "-0.002", "currency": "BTC"},
        "id": "f2b",
    }

    result = convert_transaction([f1_q, f1_b, f2_q, f2_b], config)

    # Should have 2 separate transaction blocks (separated by \n\n)
    parts = result.split("\n\n")
    assert len(parts) == 2

    assert "f1b f1q" in parts[0]
    assert "f2b f2q" in parts[1]

    # Verify each block has its own commission postings
    expected_fees = [
        ("Expenses:Fees:Coinbase  1.0 USD", "Expenses:Fees:Coinbase  1 USD"),
        ("Assets:Coinbase:USD  -1.0 USD", "Assets:Coinbase:USD  -1 USD"),
        ("Expenses:Fees:Coinbase  2.0 USD", "Expenses:Fees:Coinbase  2 USD"),
        ("Assets:Coinbase:USD  -2.0 USD", "Assets:Coinbase:USD  -2 USD"),
    ]

    fill_pairs = [
        (expected_fees[0], expected_fees[1]),
        (expected_fees[2], expected_fees[3]),
    ]
    for part, fees in zip(parts, fill_pairs):
        f1, f2 = fees
        assert f1[0] in part or f1[1] in part
        assert f2[0] in part or f2[1] in part


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
            "product_id": "BTC-USD",
        },
        "amount": {"amount": "0.002", "currency": "BTC"},
        "id": "id",
    }

    declarations = generate_declarations([txn], config)
    assert "open Assets:Coinbase:USD" in declarations
    assert "open Expenses:Fees:Coinbase" in declarations
