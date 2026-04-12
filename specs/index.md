# Coinbase to Beancount Specifications

This directory contains detailed technical specifications for the `cb2bc` tool. These specifications provide enough detail to recreate the core functionality of the application.

## Index

1.  **[Authentication](authentication.md)**
    - Details of the Coinbase CDP API JWT authentication process, including header requirements and payload structure.
2.  **[API Client](api-client.md)**
    - Specification of the `CoinbaseClient`, including request handling, pagination logic, and the offline fixture system (record/replay).
3.  **[CLI](cli.md)**
    - Description of the command-line interface, argument parsing, and the overall execution flow.
4.  **[Converter](converter.md)**
    - Deep dive into transaction processing, merging related transactions, pairing Advanced Trade Fills, and generating Beancount-formatted output.
5.  **[Configuration](configuration.md)**
    - Explanation of the configuration system, environment variable overrides, and account mapping logic.
