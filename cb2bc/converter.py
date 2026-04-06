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


def _get_fee(txn: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Extract fee amount and currency from transaction data"""
    # Try root 'fee' field
    if fee := txn.get("fee"):
        return fee.get("amount"), fee.get("currency")

    # Try 'network' field (often for sends/buys)
    if (network := txn.get("network")) and (fee := network.get("transaction_fee")):
        return fee.get("amount"), fee.get("currency")

    # Try 'buy' or 'sell' associated resources if they exist
    # (Sometimes fees are in the sub-resource)
    for sub in ("buy", "sell"):
        if resource := txn.get(sub):
            if fee := resource.get("fee"):
                return fee.get("amount"), fee.get("currency")
            # Calculate fee as difference between total and subtotal
            # if explicit fee is missing
            total = resource.get("total", {})
            subtotal = resource.get("subtotal", {})
            if total.get("amount") and subtotal.get("amount"):
                fee_val = abs(Decimal(total["amount"]) - Decimal(subtotal["amount"]))
                if fee_val > 0:
                    return str(fee_val), total.get("currency")

    return None, None


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

    # Extract fee and adjust fiat amounts if buy/sell sub-resource exists
    fee_amount, fee_currency = _get_fee(txn)

    # For buy/sell, prioritize the sub-resource for amounts if available
    resource = txn.get(txn_type) if txn_type in ("buy", "sell") else None
    sub_res_subtotal = {}
    if resource:
        # subtotal = gross (before fee, used for unit price)
        # total = net (after fee, used for cash flow)
        sub_res_total = resource.get("total", {})
        sub_res_subtotal = resource.get("subtotal", {})

        if sub_res_subtotal.get("amount"):
            # Use subtotal as the gross fiat value for price calculation
            fiat_amount = sub_res_subtotal.get("amount")
            fiat_currency = sub_res_subtotal.get("currency")

        if sub_res_total.get("amount"):
            # Use total as the net fiat amount for the balancing leg
            net_fiat_amount = sub_res_total.get("amount")
        else:
            net_fiat_amount = fiat_amount
    else:
        net_fiat_amount = fiat_amount

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
    fee_account = get_account_for_transaction(txn_type, "fee", config)

    # Format transaction based on type
    lines = [f'{date_str} * "{description}" ^coinbase-{txn_id}']
    lines.extend(metadata_lines)

    if txn_type == "buy":
        # Calculate price
        if fiat_amount and fiat_currency:
            crypto_dec = Decimal(crypto_amount)
            # gross_fiat is the value before fee
            gross_fiat = Decimal(fiat_amount)
            price = abs(gross_fiat / crypto_dec)

            # Using '@' for buy too can avoid cost matching issues in generated output
            # though '{price}' is more standard for acquisitions.
            lines.append(
                f"  {crypto_account}  {crypto_amount} "
                f"{crypto_currency} @ {price:.2f} {fiat_currency}"
            )
            if fee_amount and fee_currency:
                lines.append(f"  {fee_account}  {fee_amount} {fee_currency}")
            if other_account:
                # Deduct total fiat amount (net received by Coinbase) from checking
                lines.append(f"  {other_account}  -{net_fiat_amount} {fiat_currency}")
        else:
            lines.append(f"  {crypto_account}  {crypto_amount} {crypto_currency}")
            if other_account:
                lines.append(f"  {other_account}")

    elif txn_type == "sell":
        # Calculate price
        if fiat_amount and fiat_currency:
            crypto_dec = Decimal(crypto_amount)
            # gross_fiat is the value before fee
            gross_fiat = Decimal(fiat_amount)
            price = abs(gross_fiat / crypto_dec)

            # For sells, Beancount needs the price annotation '@' or cost reduction '{}'
            # Note: The sum of postings must be zero.
            # Crypto Value (Gross) + Fee (Expense) + Fiat Received (Income) = 0
            # Example: Sold 1 BTC for 60k USD, 3 USD fee.
            # Assets:Coinbase:BTC  -1 BTC @ 60000 USD  -> +60000 USD
            # Expenses:Fees          3 USD             -> +3 USD
            # Assets:Bank:Checking  59997 USD          -> -59997 USD
            # Wait, Beancount signs:
            # Assets:Coinbase:BTC   -1 BTC @ 60000 USD (+/- based on balance)
            # Actually, standard sell is:
            # Assets:Coinbase:BTC   -1 BTC @ 60000 USD
            # Expenses:Fees          3 USD
            # Assets:Bank:Checking  59997 USD
            # This balances if 60000 - 3 - 59997 = 0? No.
            # If I sell 1 BTC @ 60k, I get 60k. If I pay 3 fee, I have 59997.
            # Posting 1: -1 BTC @ 60k = -60000 USD
            # Posting 2: 3 USD
            # Posting 3: 59997 USD
            # Sum: -60000 + 3 + 59997 = 0. Correct.

            lines.append(
                f"  {crypto_account}  {crypto_amount} "
                f"{crypto_currency} @ {price:.2f} {fiat_currency}"
            )
            if fee_amount and fee_currency:
                lines.append(f"  {fee_account}  {fee_amount} {fee_currency}")
            if other_account:
                # Calculate net received if not explicitly provided
                fee_dec = Decimal(fee_amount) if fee_amount else Decimal("0")
                if not sub_res_subtotal.get("amount") and fee_dec:
                    net_received = gross_fiat - fee_dec
                else:
                    net_received = abs(Decimal(net_fiat_amount))

                # Add net fiat amount (received in bank) to checking
                lines.append(f"  {other_account}  {net_received} {fiat_currency}")
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

        fee_amount, _ = _get_fee(txn)
        if fee_amount:
            fee_account = get_account_for_transaction(txn_type, "fee", config)
            if fee_account:
                accounts.add(fee_account)

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
