# cb2bc/cli.py
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from cb2bc.api import CoinbaseAPIError, CoinbaseClient
from cb2bc.config import load_config
from cb2bc.converter import convert_transaction, generate_declarations


@click.command()
@click.option("--from", "from_date", type=str, help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", type=str, help="End date (YYYY-MM-DD)")
@click.option("--account", type=str, help="Specific account ID")
@click.option("--output", type=click.Path(), help="Output file path")
@click.option("--append", is_flag=True, help="Append to output file")
@click.option(
    "--config", "config_path", type=click.Path(exists=True), help="Config file path"
)
@click.option(
    "--verbose", "-v", count=True, help="Verbose output (use -vv for even more)"
)
@click.option("--record", type=click.Path(), help="Directory to record API responses")
def main(
    from_date: Optional[str],
    to_date: Optional[str],
    account: Optional[str],
    output: Optional[str],
    append: bool,
    config_path: Optional[str],
    verbose: int,
    record: Optional[str] = None,
):
    """Fetch Coinbase transactions and convert to beancount format"""

    # Load configuration
    if config_path:
        config_file = Path(config_path)
    else:
        config_file = Path.home() / ".config" / "coinbase-beancount" / "config.json"
    config = load_config(config_file)

    # Check for credentials
    fixture_dir = config.get("fixture_dir")
    if not fixture_dir and (
        not config.get("key_name") or not config.get("private_key")
    ):
        msg = (
            "Error: Missing credentials. Set COINBASE_KEY_NAME and "
            "COINBASE_PRIVATE_KEY or add to config file."
        )
        click.echo(msg, err=True)
        sys.exit(1)

    # Parse dates
    start_date = datetime.fromisoformat(from_date) if from_date else None
    end_date = datetime.fromisoformat(to_date) if to_date else None

    if start_date and end_date and end_date < start_date:
        click.echo("Error: End date must be after start date", err=True)
        sys.exit(1)

    try:
        # Initialize API client
        client = CoinbaseClient(
            config.get("key_name"),
            config.get("private_key"),
            debug=(verbose >= 2),
            record_dir=record,
            fixture_dir=fixture_dir,
        )

        # Get accounts
        if account:
            account_ids = [account]
        else:
            if verbose >= 1:
                click.echo("Discovering accounts...", err=True)
            accounts = client.get_accounts()
            account_ids = [acc["id"] for acc in accounts]
            if verbose >= 1:
                click.echo(f"Found {len(account_ids)} accounts", err=True)

        # Fetch transactions
        all_transactions = []
        for acc_id in account_ids:
            if verbose >= 1:
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
            with open(output, mode, encoding="utf-8") as f:
                f.write(output_text)
            click.echo(f"Wrote to {output}", err=True)
        else:
            click.echo(output_text)

        # Summary
        if verbose >= 1:
            click.echo(
                f"\nConverted {converted_count} transactions ({skipped_count} skipped)",
                err=True,
            )

    except CoinbaseAPIError as e:
        click.echo(f"API Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose >= 1:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
