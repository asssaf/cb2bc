# cb2bc/converter.py
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from cb2bc.mappings import get_account_for_transaction, get_default_mappings


def format_commodity(currency: str) -> str:
    """Format commodity declaration for beancount"""
    return f"1970-01-01 commodity {currency}"


def collect_commodities(transactions: list) -> set[str]:
    """Collect unique currencies from transactions"""
    commodities = set()
    for txn in transactions:
        if amount := txn.get("amount"):
            commodities.add(amount.get("currency"))
        if native := txn.get("native_amount"):
            commodities.add(native.get("currency"))
    return commodities


def convert_transaction(txn: dict[str, Any], config: dict[str, Any]) -> Optional[str]:
    """
    Convert Coinbase transaction to beancount format.
    Returns None if transaction should be skipped.
    """
    # Extract basic fields
    txn_id = txn.get("id")
    txn_type = txn.get("type")
    status = txn.get("status")
    created_at = txn.get("created_at")
    description = txn.get("description", txn_type.replace("_", " ").title())

    # Skip if not completed
    if status != "completed":
        return None

    # Parse amounts
    amount = txn.get("amount", {})
    crypto_amount = amount.get("amount")
    crypto_currency = amount.get("currency")

    native = txn.get("native_amount", {})
    fiat_amount = native.get("amount")
    fiat_currency = native.get("currency")

    if not crypto_amount or not crypto_currency:
        return None

    # Parse date
    date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    date_str = date.strftime("%Y-%m-%d")

    # Build metadata
    metadata_lines = [
        f'  coinbase_id: "{txn_id}"',
        f'  coinbase_timestamp: "{created_at}"',
    ]

    # Get accounts
    prefix = config.get("account_prefix", "Assets:Coinbase")
    crypto_account = f"{prefix}:{crypto_currency}"

    mappings = get_default_mappings()
    category = mappings.get(txn_type, "transfer")
    other_account = get_account_for_transaction(txn_type, category, config)

    # Format transaction based on type
    lines = [f'{date_str} * "{description}" ^coinbase-{txn_id}']
    lines.extend(metadata_lines)

    if txn_type == "buy":
        # Calculate price
        if fiat_amount and fiat_currency:
            crypto_dec = Decimal(crypto_amount)
            fiat_dec = Decimal(fiat_amount)
            price = abs(fiat_dec / crypto_dec)
            lines.append(
                f"  {crypto_account}  {crypto_amount} "
                f"{crypto_currency} {{{price:.2f} {fiat_currency}}}"
            )
            if other_account:
                # Deduct fiat amount from checking
                lines.append(f"  {other_account}  -{fiat_amount} {fiat_currency}")
        else:
            lines.append(f"  {crypto_account}  {crypto_amount} {crypto_currency}")
            if other_account:
                lines.append(f"  {other_account}")

    elif txn_type == "sell":
        # Calculate price
        if fiat_amount and fiat_currency:
            crypto_dec = Decimal(crypto_amount)
            fiat_dec = Decimal(fiat_amount)
            # Crypto amount is negative for sells
            price = abs(fiat_dec / crypto_dec)
            # For sells, Beancount needs the price annotation '@' or cost reduction '{}'
            # To handle cost reduction correctly without 'no position matches',
            # using 'at price' syntax is often simpler for generated output
            # unless we track inventory.
            lines.append(
                f"  {crypto_account}  {crypto_amount} "
                f"{crypto_currency} @ {price:.2f} {fiat_currency}"
            )
            if other_account:
                # Add fiat amount to checking
                lines.append(f"  {other_account}  {abs(fiat_dec)} {fiat_currency}")
        else:
            lines.append(f"  {crypto_account}  {crypto_amount} {crypto_currency}")
            if other_account:
                lines.append(f"  {other_account}")

    elif category == "staking" or category == "income":
        lines.append(f"  {crypto_account}  {crypto_amount} {crypto_currency}")
        if other_account:
            lines.append(f"  {other_account}")

    else:
        # Generic transfer (send/receive)
        lines.append(f"  {crypto_account}  {crypto_amount} {crypto_currency}")
        if other_account:
            lines.append(f"  {other_account}")

    return "\n".join(lines)


def collect_accounts(transactions: list, config: dict[str, Any]) -> set[str]:
    """Collect all accounts used in transactions"""
    accounts = set()
    prefix = config.get("account_prefix", "Assets:Coinbase")
    mappings = get_default_mappings()

    for txn in transactions:
        if amount := txn.get("amount"):
            currency = amount.get("currency")
            if currency:
                accounts.add(f"{prefix}:{currency}")

        txn_type = txn.get("type")
        category = mappings.get(txn_type, "transfer")
        other_account = get_account_for_transaction(txn_type, category, config)
        if other_account:
            accounts.add(other_account)

    return accounts


def generate_declarations(transactions: list, config: dict[str, Any]) -> str:
    """Generate commodity and account declarations"""
    lines = []

    # Commodities
    commodities = collect_commodities(transactions)
    for commodity in sorted(commodities):
        lines.append(format_commodity(commodity))

    if commodities:
        lines.append("")

    # Accounts
    accounts = collect_accounts(transactions, config)
    for account in sorted(accounts):
        lines.append(f"1970-01-01 open {account}")

    if accounts:
        lines.append("")

    return "\n".join(lines)
