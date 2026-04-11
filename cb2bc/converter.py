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
    # Try advanced_trade_fill
    if (
        (atf := txn.get("advanced_trade_fill"))
        and isinstance(atf, dict)
        and (commission := atf.get("commission"))
    ):
        return commission, "USD"

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


def get_shared_id(txn: dict[str, Any]) -> Optional[str]:
    """Extract shared ID from buy, sell, or trade fields or advanced_trade_fill"""
    for key in ("buy", "sell", "trade"):
        resource = txn.get(key)
        if isinstance(resource, dict) and (shared_id := resource.get("id")):
            return shared_id

    if (
        (atf := txn.get("advanced_trade_fill"))
        and isinstance(atf, dict)
        and (order_id := atf.get("order_id"))
    ):
        return order_id

    return None


def _group_atf_into_fills(txns: list[dict[str, Any]]) -> list[tuple[dict, dict]]:
    """Group advanced_trade_fill transactions into pairs (fills)"""
    quote_txns = []
    base_txns = []

    for t in txns:
        currency = t.get("amount", {}).get("currency")
        if currency in ("USD", "USDC"):
            quote_txns.append(t)
        else:
            base_txns.append(t)

    fills = []
    used_quote_ids = set()

    for base in base_txns:
        atf_b = base.get("advanced_trade_fill", {})
        # Find a matching quote
        match = None
        for quote in quote_txns:
            if quote["id"] in used_quote_ids:
                continue
            atf_q = quote.get("advanced_trade_fill", {})
            if (
                atf_b.get("commission") == atf_q.get("commission")
                and atf_b.get("fill_price") == atf_q.get("fill_price")
                and atf_b.get("product_id") == atf_q.get("product_id")
                and base.get("created_at") == quote.get("created_at")
            ):
                match = quote
                break

        if match:
            fills.append((base, match))
            used_quote_ids.add(match["id"])
        else:
            # Should not happen based on requirements, but handle gracefully
            fills.append((base, {}))

    # Add remaining quotes as partial fills if any (should not happen normally)
    for quote in quote_txns:
        if quote["id"] not in used_quote_ids:
            fills.append(({}, quote))

    return fills


def _convert_atf_fill(
    base: dict[str, Any], quote: dict[str, Any], config: dict[str, Any]
) -> Optional[str]:
    """Convert a single ATF fill (pair of transactions) to beancount"""
    main_txn = base if base else quote
    if not main_txn:
        return None

    atf = main_txn.get("advanced_trade_fill", {})
    order_id = atf.get("order_id")
    created_at = main_txn.get("created_at")
    date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    date_str = date.strftime("%Y-%m-%d")

    lines = [f'{date_str} * "Advanced Trade Fill" ^coinbase-{order_id}']
    lines.append(f'  coinbase_trade_id: "{order_id}"')

    txn_ids = [t.get("id") for t in (base, quote) if t.get("id")]
    lines.append(f'  coinbase_id: "{" ".join(txn_ids)}"')
    lines.append(f'  coinbase_timestamp: "{created_at}"')

    prefix = config.get("account_prefix", "Assets:Coinbase")

    # Base leg
    if base:
        amount = base.get("amount", {})
        curr = amount.get("currency")
        dec = Decimal(amount.get("amount", "0"))

        # Calculate total price from quote amount to avoid rounding errors
        quote_amount = quote.get("amount", {}) if quote else {}
        total_price = abs(Decimal(quote_amount.get("amount", "0")))
        lines.append(f"  {prefix}:{curr}  {dec:f} {curr} @@ {total_price:f} USD")

        # Commission
        commission = atf.get("commission")
        if commission:
            fee_acc = get_account_for_transaction("advanced_trade_fill", "fee", config)
            comm_dec = Decimal(commission)
            lines.append(f"  {fee_acc}  {comm_dec:f} USD")
            lines.append(f"  {prefix}:USD  -{comm_dec:f} USD")

    # Quote leg
    if quote:
        amount = quote.get("amount", {})
        curr = amount.get("currency")
        dec = Decimal(amount.get("amount", "0"))

        # Fix bug where quote amount is positive on 'buy' orders
        if atf.get("order_side") == "buy" and dec > 0:
            dec = -dec

        if curr == "USDC":
            lines.append(f"  {prefix}:{curr}  {dec:f} {curr} @ 1.00 USD")
        else:
            lines.append(f"  {prefix}:{curr}  {dec:f} {curr}")

    return "\n".join(lines)


def convert_transaction(txns: Any, config: dict[str, Any]) -> Optional[str]:
    """
    Convert Coinbase transaction(s) to beancount format.
    Accepts a single transaction dict or a list of related transactions.
    Returns None if transaction(s) should be skipped.
    """
    if isinstance(txns, dict):
        txns = [txns]

    # Filter out non-completed transactions
    txns = [t for t in txns if t.get("status") == "completed"]
    if not txns:
        return None

    # Handle advanced_trade_fill specifically by splitting into separate fills
    if all(t.get("type") == "advanced_trade_fill" for t in txns):
        fills = _group_atf_into_fills(txns)
        results = []
        for base, quote in fills:
            entry = _convert_atf_fill(base, quote, config)
            if entry:
                results.append(entry)
        return "\n\n".join(results) if results else None

    # Sort by created_at
    txns.sort(key=lambda t: t.get("created_at", ""))

    first_txn = txns[0]
    created_at = first_txn.get("created_at")
    date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    date_str = date.strftime("%Y-%m-%d")

    # Shared ID for link
    shared_id = None
    for t in txns:
        shared_id = get_shared_id(t)
        if shared_id:
            break

    link_id = shared_id if shared_id else first_txn.get("id")

    # Descriptions
    descriptions = []
    for t in txns:
        desc = t.get("description", t.get("type", "").replace("_", " ").title())
        if desc and desc not in descriptions:
            descriptions.append(desc)
    description = " / ".join(descriptions)

    lines = [f'{date_str} * "{description}" ^coinbase-{link_id}']

    # Metadata
    txn_ids = " ".join([t.get("id", "") for t in txns])
    lines.append(f'  coinbase_id: "{txn_ids}"')
    lines.append(f'  coinbase_timestamp: "{created_at}"')
    if shared_id:
        lines.append(f'  coinbase_trade_id: "{shared_id}"')

    # Collect postings and balance (in fiat equivalent)
    postings = []
    fees = []
    fiat_balance = Decimal("0")
    fiat_currency = None

    prefix = config.get("account_prefix", "Assets:Coinbase")
    mappings = get_default_mappings()

    for t in txns:
        txn_type = t.get("type")
        amount = t.get("amount", {})
        crypto_amount = amount.get("amount")
        crypto_currency = amount.get("currency")

        if not crypto_amount or not crypto_currency:
            continue

        native = t.get("native_amount", {})
        txn_fiat_amount = native.get("amount")
        txn_fiat_currency = native.get("currency")

        if txn_fiat_currency:
            fiat_currency = txn_fiat_currency

        crypto_account = f"{prefix}:{crypto_currency}"
        crypto_dec = Decimal(crypto_amount)

        # Fee collection (deduplicated)
        fee_amt, fee_curr = _get_fee(t)
        if fee_amt and fee_curr and (fee_amt, fee_curr) not in fees:
            fees.append((fee_amt, fee_curr))

        # Handle buy/sell specifics
        resource = t.get(txn_type) if txn_type in ("buy", "sell") else None
        gross_fiat_amount = None
        if resource:
            sub_res_subtotal = resource.get("subtotal", {})
            if crypto_currency not in ("USD", "USDC"):
                gross_fiat_amount = sub_res_subtotal.get("amount") or txn_fiat_amount
        else:
            gross_fiat_amount = txn_fiat_amount

        if gross_fiat_amount and crypto_currency not in ("USD", "USDC"):
            gross_fiat_dec = abs(Decimal(gross_fiat_amount))
            postings.append(
                f"  {crypto_account}  {crypto_amount} {crypto_currency} "
                f"@@ {gross_fiat_dec} {txn_fiat_currency}"
            )
            # The value of this posting is positive if we gain crypto,
            # negative if we lose
            fiat_balance += gross_fiat_dec if crypto_dec >= 0 else -gross_fiat_dec
        else:
            if crypto_currency == "USDC":
                postings.append(
                    f"  {crypto_account}  {crypto_amount} {crypto_currency} @ 1.00 USD"
                )
            else:
                postings.append(
                    f"  {crypto_account}  {crypto_amount} {crypto_currency}"
                )

            if crypto_currency in ("USD", "USDC"):
                # Fiat posting directly affects balance
                fiat_balance += crypto_dec
            elif txn_fiat_amount:
                # Other crypto legs without @@ use native_amount for balancing
                fiat_balance += Decimal(txn_fiat_amount)

    # Add fee postings
    for f_amt, f_curr in fees:
        fee_account = get_account_for_transaction(first_txn.get("type"), "fee", config)
        postings.append(f"  {fee_account}  {f_amt} {f_curr}")
        # Fees are expenses (fiat inflow to the expense account, outflow from assets)
        fiat_balance += Decimal(f_amt)

    # Add balancing leg if needed
    if abs(fiat_balance) > Decimal("0.00000001"):
        txn_type = first_txn.get("type")
        # For merged transactions, the balancing leg is usually the fee
        category = "fee" if len(txns) > 1 else mappings.get(txn_type, "transfer")
        other_account = get_account_for_transaction(txn_type, category, config)

        # Use implicit balancing for single transactions
        if len(txns) == 1:
            postings.append(f"  {other_account}")
        else:
            # For merged transactions, use explicit balancing amount to be safe
            balancing_amount = -fiat_balance
            if fiat_currency:
                postings.append(
                    f"  {other_account}  {balancing_amount} {fiat_currency}"
                )
            else:
                postings.append(f"  {other_account}  {balancing_amount}")
    elif len(postings) == 1 or (
        len(txns) == 1 and first_txn.get("type") in ("buy", "sell")
    ):
        # Balanced but only one posting, OR single-sided buy/sell that happens
        # to be balanced (should not happen normally but for safety)
        txn_type = first_txn.get("type")
        category = mappings.get(txn_type, "transfer")
        other_account = get_account_for_transaction(txn_type, category, config)
        postings.append(f"  {other_account}")

    lines.extend(postings)
    return "\n".join(lines)


def collect_accounts(transactions: list, config: dict[str, Any]) -> set[str]:
    """Collect all accounts used in transactions"""
    accounts = set()
    prefix = config.get("account_prefix", "Assets:Coinbase")
    mappings = get_default_mappings()

    # Identify transaction groups
    groups = {}
    for txn in transactions:
        shared_id = get_shared_id(txn)
        if shared_id:
            if shared_id not in groups:
                groups[shared_id] = []
            groups[shared_id].append(txn)
        else:
            groups[txn["id"]] = [txn]

    for txn_group in groups.values():
        is_atf = all(t.get("type") == "advanced_trade_fill" for t in txn_group)
        for txn in txn_group:
            if amount := txn.get("amount"):
                currency = amount.get("currency")
                if currency:
                    accounts.add(f"{prefix}:{currency}")

            txn_type = txn.get("type")
            fee_amount, _ = _get_fee(txn)
            if fee_amount:
                fee_account = get_account_for_transaction(txn_type, "fee", config)
                if fee_account:
                    accounts.add(fee_account)
                if is_atf:
                    accounts.add(f"{prefix}:USD")

        # Other side accounts
        first_txn = txn_group[0]
        txn_type = first_txn.get("type")
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
