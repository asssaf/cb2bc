# tests/test_config.py
import os
from pathlib import Path
from cb2bc.config import load_config

def test_load_config_with_defaults():
    """When no config file exists, returns default configuration"""
    config = load_config(config_path=Path("/nonexistent"))
    assert config["account_prefix"] == "Assets:Coinbase"
    assert config["key_name"] is None
    assert config["private_key"] is None
    assert "default_accounts" in config

def test_load_config_from_file(tmp_path):
    """Load configuration from JSON file"""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"key_name": "test_key_name", "private_key": "test_private_key", "account_prefix": "Custom"}')

    config = load_config(config_path=config_file)
    assert config["key_name"] == "test_key_name"
    assert config["private_key"] == "test_private_key"
    assert config["account_prefix"] == "Custom"

def test_env_var_overrides_config_file(tmp_path, monkeypatch):
    """Environment variable takes precedence over config file"""
    config_file = tmp_path / "config.json"
    config_file.write_text('{"key_name": "file_key"}')

    monkeypatch.setenv("COINBASE_KEY_NAME", "env_key")
    config = load_config(config_path=config_file)

    assert config["key_name"] == "env_key"
