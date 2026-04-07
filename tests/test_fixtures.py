import os
import shutil
import tempfile
from pathlib import Path

import responses

from cb2bc.api import CoinbaseClient

# Load test EC private key
TEST_KEY_PATH = Path(__file__).parent / "fixtures" / "test_ec_key.pem"
TEST_PRIVATE_KEY = TEST_KEY_PATH.read_text()


@responses.activate
def test_record_and_playback():
    """Test that we can record API responses and play them back"""
    # Create temp directories for recording and playback
    record_dir = tempfile.mkdtemp()

    try:
        # 1. Record session
        responses.add(
            responses.GET,
            "https://api.coinbase.com/v2/accounts",
            json={
                "pagination": {"next_uri": None},
                "data": [{"id": "acc-1", "name": "Test Account"}],
            },
            status=200,
        )

        client_record = CoinbaseClient(
            key_name="test_key", private_key=TEST_PRIVATE_KEY, record_dir=record_dir
        )
        accounts = client_record.get_accounts()

        assert len(accounts) == 1
        assert accounts[0]["id"] == "acc-1"

        # Verify fixture file was created
        fixture_file = Path(record_dir) / "GET_v2_accounts.json"
        assert fixture_file.exists()

        # 2. Playback session (no credentials, no mock responses needed)
        # Note: responses.activate is still active but should not see any requests
        client_playback = CoinbaseClient(fixture_dir=record_dir)

        # This should load from the record_dir and NOT make a real request
        # (If it tried to make a request, it would fail because no mock is set
        # or it would fail because no credentials)
        accounts_playback = client_playback.get_accounts()

        assert len(accounts_playback) == 1
        assert accounts_playback[0]["id"] == "acc-1"
        assert accounts_playback[0]["name"] == "Test Account"

    finally:
        shutil.rmtree(record_dir)


@responses.activate
def test_playback_with_pagination():
    """Test playback with paginated results"""
    record_dir = tempfile.mkdtemp()

    try:
        # Record paginated responses
        responses.add(
            responses.GET,
            "https://api.coinbase.com/v2/accounts",
            json={
                "pagination": {"next_uri": "/v2/accounts?starting_after=acc-1"},
                "data": [{"id": "acc-1"}],
            },
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.coinbase.com/v2/accounts?starting_after=acc-1",
            json={
                "pagination": {"next_uri": None},
                "data": [{"id": "acc-2"}],
            },
            status=200,
        )

        client_record = CoinbaseClient(
            key_name="test_key", private_key=TEST_PRIVATE_KEY, record_dir=record_dir
        )
        client_record.get_accounts()

        # Verify both pages were recorded
        assert (Path(record_dir) / "GET_v2_accounts.json").exists()
        assert (Path(record_dir) / "GET_v2_accounts_starting_after=acc-1.json").exists()

        # Playback
        client_playback = CoinbaseClient(fixture_dir=record_dir)
        accounts = client_playback.get_accounts()

        assert len(accounts) == 2
        assert accounts[0]["id"] == "acc-1"
        assert accounts[1]["id"] == "acc-2"

    finally:
        shutil.rmtree(record_dir)
