# cb2bc/cli.py
import click
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from cb2bc.config import load_config
from cb2bc.api import CoinbaseClient, CoinbaseAPIError
from cb2bc.converter import (
    convert_transaction,
    generate_declarations
)
from cb2bc.mappings import get_default_mappings

@click.command()
@click.option("--from", "from_date", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", type=str, help="End date (YYYY-MM-DD)")
@click.option("--account", type=str, help="Specific account ID")
@click.option("--output", type=click.Path(), help="Output file path")
@click.option("--append", is_flag=True, help="Append to output file")
@click.option("--config", "config_path", type=click.Path(exists=True),
              help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def main(from_date: Optional[str], to_date: Optional[str],
         account: Optional[str], output: Optional[str],
         append: bool, config_path: Optional[str], verbose: bool):
    """Fetch Coinbase transactions and convert to beancount format"""

    # Load configuration
    config_file = Path(config_path) if config_path else Path.home() / ".config" / "coinbase-beancount" / "config.json"
    config = load_config(config_file)

    # Check for credentials
    if not config.get("key_name") or not config.get("private_key"):
        click.echo("Error: Missing credentials. Set COINBASE_KEY_NAME and COINBASE_PRIVATE_KEY or add to config file.", err=True)
        sys.exit(1)

    # Parse dates
    start_date = datetime.fromisoformat(from_date) if from_date else None
    end_date = datetime.fromisoformat(to_date) if to_date else None

    if start_date and end_date and end_date < start_date:
        click.echo("Error: End date must be after start date", err=True)
        sys.exit(1)

    try:
        # Initialize API client
        client = CoinbaseClient(config["key_name"], config["private_key"])

        # Get accounts
        if account:
            account_ids = [account]
        else:
            if verbose:
                click.echo("Discovering accounts...", err=True)
            accounts = client.get_accounts()
            account_ids = [acc["id"] for acc in accounts]
            if verbose:
                click.echo(f"Found {len(account_ids)} accounts", err=True)

        # Fetch transactions
        all_transactions = []
        for acc_id in account_ids:
            if verbose:
                click.echo(f"Fetching transactions for {acc_id}...", err=True)
            transactions = client.get_transactions(acc_id, start_date, end_date)
            all_transactions.extend(transactions)

        # Convert transactions
        beancount_lines = []

        # Add declarations (only for new file)
        if not append:
            declarations = generate_declarations(all_transactions, config)
            if declarations:
                beancount_lines.append(declarations)

        # Convert each transaction
        converted_count = 0
        skipped_count = 0

        for txn in sorted(all_transactions, key=lambda t: t.get("created_at", "")):
            result = convert_transaction(txn, config)
            if result:
                beancount_lines.append(result)
                beancount_lines.append("")  # Blank line between transactions
                converted_count += 1
            else:
                skipped_count += 1

        # Output
        output_text = "\n".join(beancount_lines)

        if output:
            mode = "a" if append else "w"
            Path(output).write_text(output_text, encoding="utf-8")
            click.echo(f"Wrote to {output}", err=True)
        else:
            click.echo(output_text)

        # Summary
        if verbose:
            click.echo(f"\nConverted {converted_count} transactions ({skipped_count} skipped)", err=True)

    except CoinbaseAPIError as e:
        click.echo(f"API Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            raise
        sys.exit(1)

if __name__ == "__main__":
    main()
