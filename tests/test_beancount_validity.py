import subprocess
import tempfile
import os
from cb2bc.converter import format_commodity, convert_transaction

def run_bean_check(content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.beancount', delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = subprocess.run(['bean-check', tmp_path], capture_output=True, text=True)
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
            "bank_checking": "Assets:Bank:Checking"
        }
    }

    transactions = [
        {
            "id": "txn-1",
            "type": "buy",
            "status": "completed",
            "amount": {"amount": "0.001", "currency": "BTC"},
            "native_amount": {"amount": "50.00", "currency": "USD"},
            "created_at": "2024-01-15T10:30:00Z",
            "description": "Bought BTC"
        },
        {
            "id": "txn-2",
            "type": "staking_reward",
            "status": "completed",
            "amount": {"amount": "0.05", "currency": "ETH"},
            "created_at": "2024-02-01T00:00:00Z",
            "description": "ETH2 staking reward"
        },
        {
            "id": "txn-3",
            "type": "send",
            "status": "completed",
            "amount": {"amount": "-0.1", "currency": "BTC"},
            "created_at": "2024-03-01T12:00:00Z",
            "description": "Sent to external wallet"
        }
    ]

    beancount_content = ""
    # Add commodity declarations
    beancount_content += format_commodity("BTC") + "\n"
    beancount_content += format_commodity("ETH") + "\n"
    beancount_content += format_commodity("USD") + "\n\n"

    # Add account declarations (optional but good practice for bean-check)
    beancount_content += "1970-01-01 open Assets:Coinbase:BTC\n"
    beancount_content += "1970-01-01 open Assets:Coinbase:ETH\n"
    beancount_content += "1970-01-01 open Assets:Bank:Checking\n"
    beancount_content += "1970-01-01 open Income:Staking\n"
    beancount_content += "1970-01-01 open Equity:Transfers\n\n"

    for txn in transactions:
        txn_content = convert_transaction(txn, config)
        if txn_content:
            # For "send" type transactions, ensure they balance by adding an balancing account
            if txn["type"] == "send":
                txn_content += "\n  Equity:Transfers"
            beancount_content += txn_content + "\n"

    returncode, stdout, stderr = run_bean_check(beancount_content)

    assert returncode == 0, f"bean-check failed with return code {returncode}\nSTDOUT: {stdout}\nSTDERR: {stderr}\n\nGenerated Content:\n{beancount_content}"
