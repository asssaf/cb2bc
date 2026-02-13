# tests/test_cli.py
import responses
import json
from pathlib import Path
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
        status=200
    )

    # Mock transactions response
    responses.add(
        responses.GET,
        "https://api.coinbase.com/v2/accounts/acc-123/transactions",
        json={
            "data": [{
                "id": "txn-123",
                "type": "buy",
                "status": "completed",
                "amount": {"amount": "0.001", "currency": "BTC"},
                "native_amount": {"amount": "50.00", "currency": "USD"},
                "created_at": "2024-01-15T10:30:00Z",
                "description": "Bought BTC"
            }],
            "pagination": {"next_uri": None}
        },
        status=200
    )

    runner = CliRunner()
    result = runner.invoke(main, ["--verbose"])

    assert result.exit_code == 0
    assert "commodity BTC" in result.output
    assert "Assets:Coinbase:BTC" in result.output
