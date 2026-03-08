"""API key authentication for multi-user access.

Keys are stored as SHA-256 hashes in the api_keys table in Supabase.
Validation uses the Supabase REST API (works from any environment).
In local dev (SUPABASE_URL not set), auth is skipped automatically.

Usage:
    # Protect a single route:
    @router.get("/scan", dependencies=[Depends(require_api_key)])

    # Protect all routes in a router:
    router = APIRouter(dependencies=[Depends(require_api_key)])

Generate a key for a user:
    python -c "import secrets; print(secrets.token_urlsafe(32))"

Register it in Supabase (run once):
    curl -X POST https://YOUR_PROJECT.supabase.co/rest/v1/api_keys \\
      -H "apikey: SERVICE_KEY" -H "Authorization: Bearer SERVICE_KEY" \\
      -H "Content-Type: application/json" \\
      -d '{"key_hash": "<sha256 of key>", "name": "username"}'
"""

from __future__ import annotations

import hashlib
import logging
import os

import requests
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _supabase_lookup(key_hash: str) -> dict | None:
    """Check api_keys table via Supabase REST API. Returns row dict or None."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not url or not service_key:
        return None

    try:
        resp = requests.get(
            f"{url}/rest/v1/api_keys",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            params={"key_hash": f"eq.{key_hash}", "select": "name,is_active"},
            timeout=5,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("API key lookup failed: %s", exc)
        raise


def require_api_key(raw_key: str | None = Security(_api_key_header)) -> str:
    """FastAPI dependency that validates X-API-Key against Supabase api_keys table.

    - If SUPABASE_URL / SUPABASE_SERVICE_KEY are not set: auth skipped (dev mode).
    - If set: key is required and validated via the Supabase REST API.
    Returns the key name (e.g. "david-laptop") for logging.
    """
    supabase_configured = bool(
        os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_KEY")
    )

    if not supabase_configured:
        return "dev"

    if not raw_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    try:
        row = _supabase_lookup(key_hash)
    except Exception as exc:
        logger.error("API key validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service temporarily unavailable",
        ) from exc

    if not row or not row.get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or inactive API key",
        )

    name: str = row["name"]
    logger.debug("Authenticated request from: %s", name)
    return name

