"""
Clerk authentication.

Verifies the JWT Clerk issues to the frontend (sent as
`Authorization: Bearer <token>`) against Clerk's JWKS endpoint, and
returns the authenticated user's Clerk ID (the token's `sub` claim).

If CLERK_JWKS_URL isn't configured (e.g. local dev, or before Clerk is
wired up on the frontend), auth is not enforced and callers fall back to
whatever user_id the client supplies -- this keeps the existing demo flow
working while making it a one-env-var flip to require real auth.
"""
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from app.config import get_settings


@lru_cache
def _jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url)


def verify_clerk_token(token: str) -> str:
    """Returns the Clerk user ID (sub claim) if the token is valid.
    Raises HTTPException(401) otherwise."""
    settings = get_settings()
    if not settings.clerk_jwks_url:
        raise HTTPException(500, "Clerk auth is not configured on this server")

    try:
        signing_key = _jwk_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"Invalid authentication token: {exc}")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(401, "Token missing subject claim")
    return sub


def get_current_user_id(
    authorization: str | None = Header(default=None),
    fallback_user_id: str | None = None,
) -> str:
    """FastAPI dependency: returns the authenticated user's ID.

    - If Clerk is configured (CLERK_JWKS_URL set) and a bearer token is
      present, verifies it and returns the real Clerk user ID.
    - If Clerk is configured but no/invalid token is supplied, raises 401.
    - If Clerk is NOT configured, falls back to `fallback_user_id` (the
      user_id field the client already sends in the request body), so
      the demo/local flow keeps working until Clerk is wired up.
    """
    settings = get_settings()
    if not settings.clerk_jwks_url:
        return fallback_user_id or "demo-user"

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    return verify_clerk_token(token)
