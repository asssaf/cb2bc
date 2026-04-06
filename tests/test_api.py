# tests/test_api.py
import json
from pathlib import Path

import pytest
import responses

from cb2bc.api import CoinbaseAPIError, CoinbaseClient

# Load test EC private key
TEST_KEY_PATH = Path(__file__).parent / "fixtures" / "test_ec_key.pem"
TEST_PRIVATE_KEY = TEST_KEY_PATH.read_text()


def test_client_initialization():
    """Client initializes with key name and private key"""
    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)
    assert client.key_name == "test_key_name"
    assert client.private_key == TEST_PRIVATE_KEY
    assert client.base_url == "https://api.coinbase.com"


@responses.activate
def test_get_accounts_pagination():
    """Fetch accounts from API with pagination"""
    # Mock first page
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json={
            "pagination": {"next_uri": "/v2/accounts?starting_after=acc-2"},
            "data": [{"id": "acc-1"}, {"id": "acc-2"}],
        },
        status=200,
    )
    # Mock second page
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts?starting_after=acc-2",
        json={
            "pagination": {"next_uri": None},
            "data": [{"id": "acc-3"}],
        },
        status=200,
    )

    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)
    accounts = client.get_accounts()

    assert len(accounts) == 3
    assert accounts[0]["id"] == "acc-1"
    assert accounts[1]["id"] == "acc-2"
    assert accounts[2]["id"] == "acc-3"


@responses.activate
def test_get_accounts():
    """Fetch accounts from API"""
    # Load fixture
    fixture_path = Path(__file__).parent / "fixtures" / "accounts_response.json"
    fixture_data = json.loads(fixture_path.read_text())

    # Mock API response
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json=fixture_data,
        status=200,
    )

    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)
    accounts = client.get_accounts()

    assert len(accounts) == 2
    assert accounts[0]["id"] == "acc-btc-123"
    assert accounts[1]["currency"]["code"] == "ETH"


@responses.activate
def test_get_transactions():
    """Fetch transactions for an account"""
    fixture_path = Path(__file__).parent / "fixtures" / "transactions_response.json"
    fixture_data = json.loads(fixture_path.read_text())

    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json=fixture_data,
        status=200,
    )

    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)
    transactions = client.get_transactions("acc-123")

    assert len(transactions) == 1
    assert transactions[0]["type"] == "buy"
    assert transactions[0]["amount"]["currency"] == "BTC"


@responses.activate
def test_get_transactions_pagination():
    """Fetch transactions for an account with pagination"""
    # Mock first page
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json={
            "pagination": {"next_uri": "/v2/accounts/acc-123/transactions?starting_after=txn-2"},
            "data": [{"id": "txn-1", "type": "buy"}, {"id": "txn-2", "type": "sell"}],
        },
        status=200,
    )
    # Mock second page
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions?starting_after=txn-2",
        json={
            "pagination": {"next_uri": None},
            "data": [{"id": "txn-3", "type": "buy"}],
        },
        status=200,
    )

    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)
    transactions = client.get_transactions("acc-123")

    assert len(transactions) == 3
    assert transactions[0]["id"] == "txn-1"
    assert transactions[1]["id"] == "txn-2"
    assert transactions[2]["id"] == "txn-3"


@responses.activate
def test_unauthorized_error():
    """401 raises clear error message"""
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json={"error": "Unauthorized"},
        status=401,
    )

    client = CoinbaseClient(key_name="bad_key", private_key=TEST_PRIVATE_KEY)
    with pytest.raises(CoinbaseAPIError, match="Invalid credentials"):
        client.get_accounts()


@responses.activate
def test_debug_logging(capsys):
    """Debug mode logs requests and responses to stderr"""
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json={"data": []},
        status=200,
    )

    client = CoinbaseClient(
        key_name="test_key_name", private_key=TEST_PRIVATE_KEY, debug=True
    )
    client.get_accounts()

    captured = capsys.readouterr()
    # Check for request log
    assert ">>> GET https://api.coinbase.com/v2/accounts" in captured.err
    assert "Header: Authorization: Bearer [REDACTED]" in captured.err
    # Check for response log
    assert "<<< Status: 200" in captured.err
    assert '"data": []' in captured.err
