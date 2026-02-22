"""
auth.py — Authentication and authorization logic for the API server.
"""

import hashlib
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from ..core.config import API_KEY, CONFIRMATION_SECRET


def _extract_bearer_token(auth_header: str | None) -> str | None:
    """Vytiahne token z Authorization: Bearer <token>."""
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def is_authorized(request: Request) -> bool:
    """
    Overi API kluc v hlavicke.
    Primarne: Authorization: Bearer <GTFS_API_KEY>
    Fallback: x-api-key: <GTFS_API_KEY>
    """
    bearer = _extract_bearer_token(request.headers.get("authorization"))
    if bearer and hmac.compare_digest(bearer, API_KEY):
        return True

    x_api_key = request.headers.get("x-api-key")
    return bool(x_api_key and hmac.compare_digest(x_api_key, API_KEY))


def unauthorized_response() -> JSONResponse:
    """OpenAI-like auth error response."""
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "message": "Invalid API key.",
                "type": "invalid_request_error",
                "param": None,
                "code": "invalid_api_key",
            }
        },
    )


def sign_confirmation_message(message: str) -> str:
    """Vytvori HMAC SHA-256 podpis potvrdenia, overitelny MCP serverom."""
    return hmac.new(
        CONFIRMATION_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
