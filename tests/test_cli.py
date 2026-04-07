# tests/test_cli.py
import json
from pathlib import Path

import responses
from click.testing import CliRunner

from cb2bc.cli import main

# Load test EC private key
TEST_KEY_PATH = Path(__file__).parent / "fixtures" / "test_ec_key.pem"
TEST_PRIVATE_KEY = TEST_KEY_PATH.read_text()


def test_cli_help():
    """CLI shows help message"""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "cb2bc" in result.output or "Options:" in result.output


def test_cli_missing_api_key(monkeypatch):
    """CLI exits with error when credentials missing"""
    monkeypatch.delenv("COINBASE_KEY_NAME", raising=False)
    monkeypatch.delenv("COINBASE_PRIVATE_KEY", raising=False)
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 1
    assert "Missing credentials" in result.output


@responses.activate
def test_cli_basic_flow(tmp_path, monkeypatch):
    """End-to-end CLI test with mocked API"""
    monkeypatch.setenv("COINBASE_KEY_NAME", "test_key_name")
    monkeypatch.setenv("COINBASE_PRIVATE_KEY", TEST_PRIVATE_KEY)

    # Mock accounts response
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json={"data": [{"id": "acc-123", "currency": {"code": "BTC"}}]},
        status=200,
    )

    # Mock transactions response
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json={
            "data": [
                {
                    "id": "txn-123",
                    "type": "buy",
                    "status": "completed",
                    "amount": {"amount": "0.001", "currency": "BTC"},
                    "native_amount": {"amount": "50.00", "currency": "USD"},
                    "created_at": "2024-01-15T10:30:00Z",
                    "description": "Bought BTC",
                }
            ],
            "pagination": {"next_uri": None},
        },
        status=200,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["--verbose"])

    assert result.exit_code == 0
    assert "commodity BTC" in result.output
    assert "Assets:Coinbase:BTC" in result.output


@responses.activate
def test_cli_extra_verbose(tmp_path, monkeypatch):
    """Extra verbose mode logs API requests to stderr"""
    monkeypatch.setenv("COINBASE_KEY_NAME", "test_key_name")
    monkeypatch.setenv("COINBASE_PRIVATE_KEY", TEST_PRIVATE_KEY)

    # Mock accounts response
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts",
        json={"data": []},
        status=200,
    )

    runner = CliRunner()
    result = runner.invoke(main, ["-vv"])

    assert result.exit_code == 0
    # Check that API logs appear in stderr
    assert ">>> GET https://api.coinbase.com/v2/accounts" in result.stderr
    assert "<<< Status: 200" in result.stderr


def test_cli_replay_mode(tmp_path):
    """CLI replays responses from a directory, bypassing credentials"""
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()

    # Create a fixture file
    accounts_fixture = replay_dir / "GET_v2_accounts.json"
    accounts_fixture.write_text(
        json.dumps(
            {
                "data": [{"id": "acc-replay", "currency": {"code": "ETH"}}],
                "pagination": {"next_uri": None},
            }
        )
    )

    # Create transactions fixture
    tx_fixture = replay_dir / "GET_v2_accounts_acc-replay_transactions.json"
    tx_fixture.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "id": "txn-replay",
                        "type": "buy",
                        "status": "completed",
                        "amount": {"amount": "1.0", "currency": "ETH"},
                        "native_amount": {"amount": "2000.00", "currency": "USD"},
                        "created_at": "2024-02-01T12:00:00Z",
                        "description": "Bought ETH",
                    }
                ],
                "pagination": {"next_uri": None},
            }
        )
    )

    runner = CliRunner()
    # Run with --replay, no credentials provided
    result = runner.invoke(main, ["--replay", str(replay_dir)])

    assert result.exit_code == 0
    assert "ETH" in result.output
    # The output contains the coinbase_id metadata
    assert 'coinbase_id: "txn-replay"' in result.output
