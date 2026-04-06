import os
import subprocess
import tempfile

from cb2bc.converter import convert_transaction, generate_declarations


def run_bean_check(content):
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".beancount", delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["bean-check", tmp_path], capture_output=True, text=True
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_beancount_validity():
    config = {
        "account_prefix": "Assets:Coinbase",
        "default_accounts": {
            "staking_income": "Income:Staking",
            "fees": "Expenses:Fees:Coinbase",
            "bank_checking": "Assets:Bank:Checking",
        },
    }

    transactions = [
        {
            "id": "txn-1",
            "type": "buy",
            "status": "completed",
            "amount": {"amount": "0.001", "currency": "BTC"},
            "native_amount": {"amount": "50.00", "currency": "USD"},
            "created_at": "2024-01-15T10:30:00Z",
            "description": "Bought BTC",
        },
        {
            "id": "txn-4",
            "type": "sell",
            "status": "completed",
            "amount": {"amount": "-0.001", "currency": "BTC"},
            "native_amount": {"amount": "60.00", "currency": "USD"},
            "created_at": "2024-01-16T10:30:00Z",
            "description": "Sold BTC",
        },
        {
            "id": "txn-5",
            "type": "buy",
            "status": "completed",
            "amount": {"amount": "0.001", "currency": "BTC"},
            "native_amount": {"amount": "70.00", "currency": "USD"},
            "fee": {"amount": "1.99", "currency": "USD"},
            "created_at": "2024-01-17T10:30:00Z",
            "description": "Bought BTC with fee",
        },
        {
            "id": "txn-2",
            "type": "staking_reward",
            "status": "completed",
            "amount": {"amount": "0.05", "currency": "ETH"},
            "created_at": "2024-02-01T00:00:00Z",
            "description": "ETH2 staking reward",
        },
        {
            "id": "txn-3",
            "type": "send",
            "status": "completed",
            "amount": {"amount": "-0.1", "currency": "BTC"},
            "created_at": "2024-03-01T12:00:00Z",
            "description": "Sent to external wallet",
        },
    ]

    beancount_content = ""

    # Generate declarations using the tool's logic
    beancount_content += generate_declarations(transactions, config)

    # Convert each transaction
    for txn in transactions:
        txn_content = convert_transaction(txn, config)
        if txn_content:
            beancount_content += txn_content + "\n\n"

    returncode, stdout, stderr = run_bean_check(beancount_content)

    msg = (
        f"bean-check failed with return code {returncode}\n"
        f"STDOUT: {stdout}\nSTDERR: {stderr}\n\n"
        f"Generated Content:\n{beancount_content}"
    )
    assert returncode == 0, msg
