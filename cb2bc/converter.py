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

    # Advanced Trade Fill fees
    if (advanced := txn.get("advanced_trade_fill")) and (
        commission := advanced.get("commission")
    ):
        # Per user request, advanced trade fill commissions are always in USD
        return commission, "USD"

    return None, None


def get_shared_id(txn: dict[str, Any]) -> Optional[str]:
    """Extract shared ID from buy, sell, trade, or advanced_trade_fill fields"""
    for key in ("buy", "sell", "trade"):
        resource = txn.get(key)
        if isinstance(resource, dict) and (shared_id := resource.get("id")):
            return shared_id

    if (
        (advanced := txn.get("advanced_trade_fill"))
        and isinstance(advanced, dict)
        and (order_id := advanced.get("order_id"))
    ):
        return order_id

    return None


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

    # For advanced_trade_fill, we need to find the base/quote currencies
    # and adjust the quote currency leg by the commission.
    is_advanced_trade = any(t.get("type") == "advanced_trade_fill" for t in txns)
    quote_currency = None
    if is_advanced_trade:
        # Get product_id from any advanced_trade_fill transaction (e.g. BTC-USDC)
        for t in txns:
            if (advanced := t.get("advanced_trade_fill")) and (
                product_id := advanced.get("product_id")
            ):
                _, quote_currency = product_id.split("-")
                break

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

        # Fee collection
        fee_amt, fee_curr = _get_fee(t)

        if is_advanced_trade:
            # For advanced_trade_fill, commissions come in pairs.
            # Only take the fee from the non-quote currency side of each pair
            # to sum all unique commissions correctly.
            if crypto_currency == quote_currency:
                fee_amt, fee_curr = None, None
            # Do NOT deduplicate fees for advanced trade fills because
            # multiple fills might have the same commission amount.
            if fee_amt and fee_curr:
                fees.append((fee_amt, fee_curr))
        else:
            # For regular buys/sells, deduplicate by (amount, currency)
            if fee_amt and fee_curr and (fee_amt, fee_curr) not in fees:
                fees.append((fee_amt, fee_curr))

        crypto_account = f"{prefix}:{crypto_currency}"
        crypto_dec = Decimal(crypto_amount)

        # Handle buy/sell specifics
        resource = t.get(txn_type) if txn_type in ("buy", "sell") else None
        gross_fiat_amount = None
        fill_price = None

        if resource:
            sub_res_subtotal = resource.get("subtotal", {})
            if crypto_currency not in ("USD", "USDC"):
                gross_fiat_amount = sub_res_subtotal.get("amount") or txn_fiat_amount
        elif is_advanced_trade and crypto_currency != quote_currency:
            # For advanced trade, use fill_price with @ USD for base currency leg.
            if advanced := t.get("advanced_trade_fill"):
                fill_price = advanced.get("fill_price")
        else:
            gross_fiat_amount = txn_fiat_amount

        if fill_price and crypto_currency not in ("USD", "USDC"):
            fill_price_dec = Decimal(fill_price)
            postings.append(
                f"  {crypto_account}  {crypto_amount} {crypto_currency} "
                f"@ {fill_price_dec} USD"
            )
            # The value of this posting is positive if we gain crypto,
            # negative if we lose
            value = abs(crypto_dec) * fill_price_dec
            fiat_balance += value if crypto_dec >= 0 else -value
        elif gross_fiat_amount and crypto_currency not in ("USD", "USDC"):
            gross_fiat_dec = abs(Decimal(gross_fiat_amount))
            postings.append(
                f"  {crypto_account}  {crypto_amount} {crypto_currency} "
                f"@@ {gross_fiat_dec} {txn_fiat_currency}"
            )
            # The value of this posting is positive if we gain crypto,
            # negative if we lose
            fiat_balance += gross_fiat_dec if crypto_dec >= 0 else -gross_fiat_dec
        else:
            # Adjust quote currency amount for advanced_trade_fill
            if is_advanced_trade and crypto_currency == quote_currency:
                # Find the commission for THIS specific fill.
                # It is reported in the matching advanced_trade_fill record for
                # the same product_id/order_id that is NOT the quote currency.
                # However, since they come in pairs with same ID, we can find it
                # by looking at the commission field of this transaction.
                commission_for_this_fill = Decimal("0")
                if (adv := t.get("advanced_trade_fill")) and (
                    comm := adv.get("commission")
                ):
                    commission_for_this_fill = Decimal(comm)

                # Net amount is gross amount minus commission.
                # For buys (negative amount), this makes it more negative.
                net_amount = crypto_dec - commission_for_this_fill

                if crypto_currency in ("USD", "USDC"):
                    postings.append(
                        f"  {crypto_account}  {net_amount} {crypto_currency} @ 1.00 USD"
                    )
                else:
                    postings.append(
                        f"  {crypto_account}  {net_amount} {crypto_currency}"
                    )
                fiat_balance += net_amount
            elif crypto_currency == "USDC":
                postings.append(
                    f"  {crypto_account}  {crypto_amount} {crypto_currency} @ 1.00 USD"
                )
                fiat_balance += crypto_dec
            else:
                postings.append(
                    f"  {crypto_account}  {crypto_amount} {crypto_currency}"
                )

                if crypto_currency == "USD":
                    # Fiat posting directly affects balance
                    fiat_balance += crypto_dec
                elif txn_fiat_amount:
                    # Other crypto legs without @@ use native_amount for balancing
                    fiat_balance += Decimal(txn_fiat_amount)

    # Consolidate fees by currency
    consolidated_fees = {}
    for f_amt, f_curr in fees:
        current_total = consolidated_fees.get(f_curr, Decimal("0"))
        consolidated_fees[f_curr] = current_total + Decimal(f_amt)

    # Add fee postings
    for f_curr, f_amt in sorted(consolidated_fees.items()):
        fee_account = get_account_for_transaction(first_txn.get("type"), "fee", config)
        postings.append(f"  {fee_account}  {f_amt} {f_curr}")
        # Fees are expenses (fiat inflow to the expense account, outflow from assets)
        fiat_balance += f_amt

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
