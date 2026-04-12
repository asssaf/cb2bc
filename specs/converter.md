# Converter Specification

The converter is responsible for transforming raw Coinbase API transaction data into valid Beancount ledger entries.

## Transaction Merging Logic

Coinbase often represents a single logical event (like a trade or a buy with a fee) as multiple discrete transaction objects in the API. The converter groups these using a shared internal ID.

### Shared ID Extraction
- Checks for an `id` field inside nested `buy`, `sell`, or `trade` resource objects.
- Checks for an `order_id` inside the `advanced_trade_fill` object.
- If no shared ID is found, the root transaction `id` is used as a fallback.

### Grouping Process
1.  All transactions across all accounts are collected.
2.  Transactions are sorted by `created_at`.
3.  Transactions sharing the same extracted internal ID are grouped into a single list for processing.

## Advanced Trade Fill (ATF) Pairing

ATF transactions require special handling because they appear as separate "base" (crypto) and "quote" (fiat/stablecoin) transactions.

1.  **Identification**: All transactions in a group must have the type `advanced_trade_fill`.
2.  **Pairing (Fills)**: Within a group, transactions are paired into "fills" based on matching:
    - `commission`
    - `fill_price`
    - `product_id`
    - `created_at` timestamp
3.  **Conversion**: Each pair is converted into a separate Beancount entry.
    - **Base Leg**: Uses the crypto amount and currency. The price is expressed using the total price operator `@@` with the absolute value of the quote amount.
    - **Quote Leg**: Uses the fiat/stablecoin amount. If it's a "buy" order but the quote amount is positive, the converter negates it.
    - **Commission**: A separate posting is created for the commission, balanced against the configured fee account and the USD asset account.

## Beancount Entry Generation

For standard (non-ATF) transactions:

1.  **Header**:
    - Date: Extracted from `created_at` (YYYY-MM-DD).
    - Status: Always `*` (cleared).
    - Description: Concatenated descriptions of all transactions in the group, joined by `" / "`.
    - Link: A link in the format `^coinbase-<ID>` is added, using the shared internal ID.
2.  **Metadata**:
    - `coinbase_id`: Space-separated list of all root transaction IDs in the group.
    - `coinbase_timestamp`: The ISO timestamp of the first transaction.
    - `coinbase_trade_id`: The shared internal ID (if applicable).
3.  **Postings**:
    - **Crypto Leg**: For buys/sells, the crypto amount is posted. If a gross fiat amount (subtotal) is available, it uses the `@@` operator with that subtotal.
    - **USDC Special Case**: USDC transactions use `@ 1.00 USD` to maintain a fixed valuation.
    - **Fees**: Fees are extracted from multiple possible locations (root `fee`, `network`, or sub-resources) and deduplicated. They are posted to the configured fee account.
    - **Balancing Leg**:
        - If the transaction is self-balancing (e.g., a crypto-to-crypto trade), no extra leg is added.
        - Otherwise, a balancing leg is added to the configured account (e.g., `Assets:Bank:Checking` or `Equity:Transfers`).
        - For single transactions, the amount is omitted (implicit balancing).
        - For merged transactions, the explicit balancing amount is calculated to ensure the entry sums to zero.

## Decimal Formatting

All amounts are formatted using fixed-point notation (e.g., Python `:f` specifier) to prevent scientific notation, which is not supported by Beancount.
