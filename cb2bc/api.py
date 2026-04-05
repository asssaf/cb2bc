# cb2bc/api.py
import secrets
import time
from datetime import datetime
from typing import Any, Optional

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

    def __init__(self, key_name: str, private_key: str):
        self.key_name = key_name
        self.private_key = private_key
        self.base_url = "https://api.coinbase.com/v2"
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
        uri = f"{method} api.coinbase.com/v2{path}"

        payload = {
            "sub": self.key_name,
            "iss": "cdp",  # Coinbase requires "cdp" as issuer
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,  # 2 minutes
            "uri": uri,
        }

        # Include required headers: kid (key name) and nonce (random hex)
        return jwt.encode(
            payload,
            private_key,
            algorithm="ES256",
            headers={"kid": self.key_name, "nonce": secrets.token_hex()},
        )

    def _request(
        self, method: str, path: str, params: Optional[dict] = None
    ) -> dict[str, Any]:
        """Make API request with JWT authentication"""
        # Generate JWT for this specific request
        token = self._generate_jwt(method, path)
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {token}"}

        response = self.session.request(
            method, url, params=params, headers=headers, timeout=30
        )

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
        """Fetch all accounts"""
        data = self._request("GET", "/accounts")
        return data.get("data", [])

    def get_transactions(
        self,
        account_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Fetch transactions for an account with pagination"""
        transactions = []
        path = f"/accounts/{account_id}/transactions"

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
                    path = next_uri.replace(self.base_url, "")
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
