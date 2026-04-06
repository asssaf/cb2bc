# Coinbase to Beancount

Fetch cryptocurrency transactions from Coinbase and convert them to [beancount](https://github.com/beancount/beancount) format.

## Installation

```bash
pip install -e .
```

## Configuration

Create `~/.config/coinbase-beancount/config.json`:

```json
{
  "key_name": "organizations/{org_id}/apiKeys/{key_id}",
  "private_key": "-----BEGIN EC PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END EC PRIVATE KEY-----",
  "account_prefix": "Assets:Coinbase",
  "default_accounts": {
    "staking_income": "Income:Staking",
    "fees": "Expenses:Fees:Coinbase",
    "bank_checking": "Assets:Bank:Checking"
  }
}
```

Or set environment variables:

```bash
export COINBASE_KEY_NAME="organizations/{org_id}/apiKeys/{key_id}"
export COINBASE_PRIVATE_KEY="-----BEGIN EC PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END EC PRIVATE KEY-----"
```

**Getting Credentials:**
1. Go to [Coinbase Developer Platform](https://portal.cdp.coinbase.com/)
2. Navigate to **API Keys** → **Secret API Keys**
3. Click **Create API key** and select **ECDSA** algorithm
4. Save your key name and private key securely

## Usage

Fetch all transactions:

```bash
cb2bc
```

Fetch with date range:

```bash
cb2bc --from 2024-01-01 --to 2024-12-31
```

Write to file:

```bash
cb2bc --from 2024-01-01 --output coinbase-2024.beancount
```

Append to existing file:

```bash
cb2bc --from 2024-01-01 --output ledger.beancount --append
```

Fetch specific account:

```bash
cb2bc --account acc-btc-123
```

Verbose output:

```bash
# Basic progress information
cb2bc --verbose

# Extra verbose mode (logs all API requests and responses)
cb2bc -vv
```

## Output Format

The tool generates valid beancount format with:

- Commodity declarations for all currencies
- Price annotations for buy/sell transactions
- Metadata (Coinbase transaction ID and timestamp)
- Links for connecting related transactions

Example output:

```beancount
1970-01-01 commodity BTC
1970-01-01 commodity USD

2024-01-15 * "Bought BTC" ^coinbase-txn-123
  coinbase_id: "txn-123"
  coinbase_timestamp: "2024-01-15T10:30:00Z"
  Assets:Coinbase:BTC  0.001 BTC {50000.00 USD}
  Assets:Bank:Checking
```

## Transaction Types

Supports all Coinbase transaction types:
- **Buy/Sell**: Trading crypto for fiat
- **Send/Receive**: Transfers to/from external wallets
- **Trade**: Crypto-to-crypto exchanges
- **Staking Rewards**: Automatically categorized as income
- **Fees**: Categorized as expenses

## Testing

To run tests and generate coverage reports, you must install the package with development dependencies:

```bash
pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```
or
```bash
python -m pytest
```

With coverage:

```bash
pytest --cov=cb2bc --cov-report=html
```

## License

MIT
