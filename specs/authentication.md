# Authentication Specification

The tool uses the Coinbase Cloud Developer Platform (CDP) API, which requires JSON Web Token (JWT) authentication for all requests.

## JWT Structure

Each request must include an `Authorization` header: `Authorization: Bearer <JWT_TOKEN>`.

### Header

The JWT header must include the following fields:
- `alg`: `ES256` (ECDSA with P-256 and SHA-256)
- `kid`: The API key name (e.g., `organizations/{org_id}/apiKeys/{key_id}`).
- `nonce`: A unique, random string (hex encoded) to prevent replay attacks.
- `typ`: `JWT`

### Payload (Claims)

The JWT payload must contain the following claims:
- `sub`: The API key name (same as `kid`).
- `iss`: The issuer, which must be exactly `"cdp"`.
- `nbf`: "Not Before" timestamp (Unix seconds). To account for clock skew, this should be set to 5 seconds in the past.
- `exp`: "Expiration" timestamp (Unix seconds). Typically set to 1 minute after creation.
- `uri`: A specific URI claim formatted as `METHOD hostname/path`.

#### URI Claim Construction

The `uri` claim is critical and must be constructed carefully:
1.  **Method**: The HTTP method (e.g., `GET`, `POST`) in uppercase.
2.  **Hostname**: The API hostname, usually `api.coinbase.com`.
3.  **Path**: The absolute path of the endpoint, including the version prefix (e.g., `/v2/accounts`).
4.  **Exclusion**: Query parameters must **not** be included in the `uri` claim.

Example URI claim: `GET api.coinbase.com/v2/accounts`

## Implementation Details

1.  **Key Loading**: The private key must be an EC private key in PEM format.
2.  **Normalization**: The request URL should be normalized before extracting the path for the `uri` claim to ensure consistency with what is actually sent to the server.
3.  **Clock Skew**: The `nbf` (not before) claim must be slightly in the past (e.g., 5 seconds) to avoid `401 Unauthorized` errors due to minor differences between the client and server clocks.
