# cb2bc/api.py
import json
import secrets
import sys
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

import jwt
import requests
from cryptography.hazmat.primitives import serialization


class CoinbaseAPIError(Exception):
    """Base exception for Coinbase API errors"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

    def __str__(self):
        if self.status_code:
            return f"{self.args[0]}: {self.status_code}"
        return f"{self.args[0]}"


class CoinbaseClient:
    """Client for Coinbase App API with JWT authentication"""

    def __init__(self, key_name: str, private_key: str, debug: bool = False):
        self.key_name = key_name
        self.private_key = private_key
        self.debug = debug
        self.base_url = "https://api.coinbase.com"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )

    def _generate_jwt(self, method: str, path: str) -> str:
        """Generate JWT token for API request using Coinbase's official method"""
        # Load the EC private key from PEM format
        private_key_bytes = self.private_key.encode("utf-8")
        private_key = serialization.load_pem_private_key(
            private_key_bytes, password=None
        )

        # Build URI: METHOD hostname/v2/path (must match actual request path)
        # Note: Coinbase CDP API documentation says the URI claim should include
        # METHOD hostname/path (query parameters are excluded from this claim)
        uri = f"{method} api.coinbase.com{path}"

        if self.debug:
            print(f"JWT URI claim: {uri}", file=sys.stderr)

        now = int(time.time())
        payload = {
            "sub": self.key_name,
            "iss": "cdp",  # Coinbase requires "cdp" as issuer
            "nbf": now - 5,  # 5 seconds in past for clock skew
            "exp": now + 60,  # 1 minute expiry
            "uri": uri,
        }

        # Include required headers: kid (key name) and nonce (random hex)
        return jwt.encode(
            payload,
            private_key,
            algorithm="ES256",
            headers={"kid": self.key_name, "nonce": secrets.token_hex()},
        )

    def _get_path_from_uri(self, uri: str) -> str:
        """Extract path from URI, handling absolute and relative paths"""
        if uri.startswith(self.base_url):
            return uri.replace(self.base_url, "")
        return uri

    def _request(
        self, method: str, path: str, params: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make API request with JWT authentication"""
        # Normalize the URL and query parameters using a PreparedRequest
        req = requests.Request(method, f"{self.base_url}{path}", params=params)
        prepared = req.prepare()

        # Extract only the path from the prepared URL for the JWT URI claim.
        # Coinbase CDP API expects the URI claim without query parameters.
        path_only = urlparse(prepared.url).path

        # Generate JWT for this specific request
        token = self._generate_jwt(method, path_only)
        prepared.headers["Authorization"] = f"Bearer {token}"

        if self.debug:
            print(f">>> {method} {prepared.url}", file=sys.stderr)
            for k, v in prepared.headers.items():
                v_log = v
                if k.lower() == "authorization":
                    v_log = "Bearer [REDACTED]"
                print(f"Header: {k}: {v_log}", file=sys.stderr)

        response = self.session.send(prepared, timeout=30)

        if self.debug:
            print(f"<<< Status: {response.status_code}", file=sys.stderr)
            try:
                print(
                    f"Response: {json.dumps(response.json(), indent=2)}",
                    file=sys.stderr,
                )
            except Exception:
                print(f"Response: {response.text}", file=sys.stderr)

        if response.status_code == 401:
            msg = (
                "Invalid credentials. Check COINBASE_KEY_NAME and COINBASE_PRIVATE_KEY."
            )
            raise CoinbaseAPIError(msg, status_code=response.status_code)
        elif response.status_code == 403:
            msg = "Insufficient permissions. Check API key scopes."
            raise CoinbaseAPIError(msg, status_code=response.status_code)
        elif response.status_code == 404:
            raise CoinbaseAPIError(
                f"Not found: {path}", status_code=response.status_code
            )
        elif response.status_code >= 500:
            msg = f"Server error: {response.status_code}"
            raise CoinbaseAPIError(msg, status_code=response.status_code)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise CoinbaseAPIError(str(e), status_code=e.response.status_code) from e
        return response.json()

    def get_accounts(self) -> list[dict[str, Any]]:
        """Fetch all accounts with pagination"""
        accounts = []
        path = "/v2/accounts"

        while path:
            data = self._request("GET", path)
            accounts.extend(data.get("data", []))

            # Check for next page
            pagination = data.get("pagination", {})
            next_uri = pagination.get("next_uri")
            path = self._get_path_from_uri(next_uri) if next_uri else None

        return accounts

    def get_transactions(
        self,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Fetch transactions for an account with pagination"""
        transactions = []
        path = f"/v2/accounts/{account_id}/transactions"

        # Build params
        params = {}
        if start_date:
            params["start_date"] = start_date.isoformat()
        if end_date:
            params["end_date"] = end_date.isoformat()

        # Handle pagination
        while path:
            try:
                data = self._request("GET", path, params=params)
                transactions.extend(data.get("data", []))

                # Check for next page
                pagination = data.get("pagination", {})
                next_uri = pagination.get("next_uri")
                if next_uri:
                    path = self._get_path_from_uri(next_uri)
                    params = {}  # Next URI includes params
                else:
                    path = None
            except CoinbaseAPIError as e:
                if e.status_code == 404:
                    # Treat 404 as no more pages (e.g., when fetching
                    # non-existent transaction pages)
                    path = None
                else:
                    raise e

        return transactions
