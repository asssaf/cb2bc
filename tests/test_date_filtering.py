from datetime import datetime, timezone
from pathlib import Path

import responses

from cb2bc.api import CoinbaseClient

# Load test EC private key
TEST_KEY_PATH = Path(__file__).parent / "fixtures" / "test_ec_key.pem"
TEST_PRIVATE_KEY = TEST_KEY_PATH.read_text()


def setup_mocks():
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json={
            "pagination": {
                "next_uri": "/v2/accounts/acc-123/transactions?starting_after=txn-2"
            },
            "data": [
                {"id": "txn-1", "created_at": "2024-03-01T12:00:00Z", "type": "buy"},
                {"id": "txn-2", "created_at": "2024-02-01T12:00:00Z", "type": "buy"},
            ],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions?starting_after=txn-2",
        json={
            "pagination": {"next_uri": None},
            "data": [
                {"id": "txn-3", "created_at": "2024-01-01T12:00:00Z", "type": "buy"}
            ],
        },
        status=200,
    )


@responses.activate
def test_get_transactions_filter_to():
    """Verify that transactions are filtered by end_date"""
    setup_mocks()
    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)

    # Only txn-2 and txn-3 should be returned if end_date is 2024-02-15
    end_date = datetime(2024, 2, 15, tzinfo=timezone.utc)
    txns = client.get_transactions("acc-123", end_date=end_date)
    assert len(txns) == 2
    assert txns[0]["id"] == "txn-2"
    assert txns[1]["id"] == "txn-3"


@responses.activate
def test_get_transactions_filter_from_optimization():
    """Verify that fetching stops early when reaching start_date"""
    setup_mocks()
    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)

    # Only txn-1 should be returned if start_date is 2024-02-15
    # AND it should NOT call the second page
    start_date = datetime(2024, 2, 15, tzinfo=timezone.utc)
    txns = client.get_transactions("acc-123", start_date=start_date)
    assert len(txns) == 1
    assert txns[0]["id"] == "txn-1"

    # Verify second page was NOT called
    second_page_calls = [
        c for c in responses.calls if "starting_after=txn-2" in c.request.url
    ]
    assert len(second_page_calls) == 0


@responses.activate
def test_get_transactions_with_naive_dates():
    """Verify that naive dates from CLI are handled correctly"""
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json={
            "pagination": {"next_uri": None},
            "data": [
                {"id": "txn-1", "created_at": "2024-03-01T12:00:00Z", "type": "buy"},
            ],
        },
        status=200,
    )

    client = CoinbaseClient(key_name="test_key_name", private_key=TEST_PRIVATE_KEY)

    # Naive date (March 2) - should match nothing as txn-1 is March 1
    start_date = datetime(2024, 3, 2)
    txns = client.get_transactions("acc-123", start_date=start_date)
    assert len(txns) == 0

    # Naive date (Feb 28) - should match txn-1
    start_date = datetime(2024, 2, 28)
    txns = client.get_transactions("acc-123", start_date=start_date)
    assert len(txns) == 1
