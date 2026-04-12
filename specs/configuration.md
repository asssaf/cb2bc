# Configuration Specification

The application uses a flexible configuration system that combines default values, a JSON configuration file, and environment variable overrides.

## Configuration Resolution Order

1.  **Defaults**: Hardcoded values in `cb2bc/config.py`.
2.  **Config File**: JSON file loaded from `~/.config/coinbase-beancount/config.json` or specified via the `--config` CLI flag.
3.  **Environment Variables**: Specific variables that override everything else.
    - `COINBASE_KEY_NAME`
    - `COINBASE_PRIVATE_KEY`

## Key Configuration Fields

- `key_name`: The API key name from Coinbase CDP.
- `private_key`: The PEM-encoded EC private key.
- `account_prefix`: The prefix for Beancount asset accounts (default: `Assets:Coinbase`). Individual assets are appended as `:CURRENCY` (e.g., `Assets:Coinbase:BTC`).
- `fixture_dir`: Path to a directory containing recorded API responses. If set, the client operates in offline-first mode.
- `default_accounts`: A mapping of transaction categories to Beancount accounts.
    - `staking_income`: Used for staking, inflation, and learning rewards (default: `Income:Staking`).
    - `interest_income`: Used for interest transactions (default: `Income:Interest`).
    - `fees`: Used for transaction fees (default: `Expenses:Fees:Coinbase`).
    - `bank_checking`: Used for the fiat side of buys and sells (default: `Assets:Bank:Checking`).
    - `transfers`: Used for deposits, withdrawals, and sends/receives (default: `Equity:Transfers`).

## Account Mapping Logic

The tool maps Coinbase transaction types to internal categories:

| Coinbase Type | Category |
| :--- | :--- |
| `receive`, `fiat_deposit`, `send`, `fiat_withdrawal` | `transfer` |
| `buy` | `buy` |
| `sell` | `sell` |
| `trade`, `advanced_trade_fill` | `trade` |
| `staking_reward`, `inflation_reward` | `staking` |
| `learning_reward` | `income` |
| `interest` | `interest` |
| `pro_fee`, `coinbase_fee` | `fee` |

When generating a posting, the tool looks up the category in the `default_accounts` configuration to determine the target Beancount account.
