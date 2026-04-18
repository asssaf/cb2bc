# CLI Specification

The Command Line Interface (CLI) is the primary entry point for the application, built using the `click` library.

## Commands and Options

- `--from`: Optional. Start date in `YYYY-MM-DD` format.
- `--to`: Optional. End date in `YYYY-MM-DD` format.
- `--account`: Optional. Filter by a specific Coinbase account ID.
- `--output`: Optional. Path to the output Beancount file. If omitted, output is printed to stdout.
- `--append`: Optional flag. Appends to the output file instead of overwriting.
- `--config`: Optional. Path to a custom `config.json` file.
- `--verbose` / `-v` / `-vv`: Multi-level verbosity.
    - No flag: Errors only.
    - `-v`: Progress information (account discovery, transaction counts).
    - `-vv`: Full debug mode, including JWT claim info and redacted HTTP request/response logging to stderr.
- `--record`: Optional. Directory to save API responses as JSON fixtures.
- `--replay`: Optional. Directory to read API responses from, enabling offline mode.

## Execution Flow

1.  **Configuration Loading**: Loads from the default path (`~/.config/coinbase-beancount/config.json`) or the path specified via `--config`. Environment variables override file settings.
2.  **Credential Validation**: Ensures API credentials or a `fixture_dir` are present.
3.  **Account Discovery**:
    - If `--account` is provided, uses only that ID.
    - Otherwise, calls `get_accounts()` to find all available accounts.
4.  **Transaction Retrieval**: Iterates through discovered accounts and calls `get_transactions()` with date filters.
5.  **Transaction Grouping**: Related Coinbase transactions are grouped together before conversion (see [Converter](converter.md)).
6.  **Conversion**:
    - If not appending, generates Beancount `commodity` and `open` account declarations based on the unique currencies and accounts found in the transactions.
    - Converts each transaction group into Beancount format.
7.  **Output**: Writes the combined output to the specified file or stdout.
8.  **Summary**: In verbose mode, displays the total number of converted and skipped transactions.
