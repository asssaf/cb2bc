# API Client Specification

The `CoinbaseClient` handles all communication with the Coinbase API, including authentication, pagination, and response persistence.

## Core Functionality

### Request Handling

All requests are funneled through an internal `_request` method that:
1.  Prepares the URL and parameters.
2.  Generates a JWT for the specific request (see [Authentication](authentication.md)).
3.  Injects the `Authorization` header.
4.  Handles standard HTTP errors (401, 403, 404, 5xx) and raises specific `CoinbaseAPIError` exceptions.

### Pagination

Coinbase API uses cursor-based pagination.
- Responses contain a `pagination` object with a `next_uri` field.
- The client must recursively or iteratively fetch pages as long as `next_uri` is present.
- `next_uri` can be a full URL or a relative path; the client must normalize this to extract the path for the next request.

### Date Filtering (Client-Side)

Since the Coinbase API does not consistently support server-side date filtering across all endpoints, the client implements this logic:
1.  Fetches transactions in reverse-chronological order (default API behavior).
2.  Parses the `created_at` timestamp (handling 'Z' suffix for UTC).
3.  Stops pagination immediately when a transaction is encountered that is older than the `start_date`.
4.  Skips individual transactions that are newer than the `end_date`.

## Offline and Fixture System

The client supports a "record and replay" mechanism for testing and offline usage.

### Recording (`record_dir`)

When a `record_dir` is provided:
1.  Every successful API response is saved as a JSON file.
2.  Filename format: `{METHOD}_{sanitized_path}_{sanitized_query}.json`.
3.  The directory is created if it doesn't exist.

### Replaying (`fixture_dir`)

When a `fixture_dir` is provided:
1.  The client first checks if a matching fixture file exists for the current request.
2.  If a fixture is found, it is loaded and returned without making a network request.
3.  In replay mode, if a fixture is found, valid API credentials (key name and private key) are **not required**.
4.  If a fixture is missing and credentials are also missing, a `CoinbaseAPIError` is raised.

## Endpoints Implemented

- `GET /v2/accounts`: Fetches all user accounts.
- `GET /v2/accounts/{account_id}/transactions`: Fetches transactions for a specific account.
