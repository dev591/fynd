"""Supabase login tokens (JWT). Secure by default: no valid token, no access.

Two ways to check a token, no extra libraries:
  1. SUPABASE_JWT_SECRET set and the token is HS256: verify the signature locally (fast, no network).
  2. Otherwise SUPABASE_URL + SUPABASE_ANON_KEY: ask Supabase's Auth server (works for any signing mode).
If neither is configured, protected routes answer 503 instead of letting anyone in.
The secret is read from the environment only. It is never written in code.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from typing import Optional

import httpx
from fastapi import HTTPException, Request, status
from pydantic import BaseModel

_REMOTE_TTL_S = 60
_remote_cache: dict[str, tuple[float, "AuthUser"]] = {}


class AuthUser(BaseModel):
    id: str
    email: Optional[str] = None


def _b64url(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


# SHA-256 of a Supabase JWT secret that was committed to a public repository. It is never trusted again, even if it is
# still in someone's .env: a leaked signing key lets anyone forge a login. Only the hash is kept here, not the secret.
REVOKED_SECRET_SHA256 = {"5de92c42ba17dbf6b93723e78a2fbfe4b8374d9a67802086af51bf581a8b0b7c"}


def _secret() -> str:
    raw = os.environ.get("SUPABASE_JWT_SECRET", "")
    if raw and hashlib.sha256(raw.encode()).hexdigest() in REVOKED_SECRET_SHA256:
        _warn_once()
        return ""                          # fall back to asking Supabase to verify each token
    return raw


_warned = False


def _warn_once() -> None:
    global _warned
    if not _warned:
        _warned = True
        print("WARNING: SUPABASE_JWT_SECRET is a secret that was published in a git repository. It is being IGNORED and "
              "logins are verified by asking Supabase instead. Rotate the secret in Supabase "
              "(Project Settings > JWT Keys) and update api/.env.", file=sys.stderr)


def _url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def _anon() -> str:
    return os.environ.get("SUPABASE_ANON_KEY", "")


def auth_configured() -> bool:
    return bool(_secret() or (_url() and _anon()))


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def verify_hs256(token: str, secret: str, now: Optional[float] = None) -> Optional[AuthUser]:
    """Check an HS256 token's signature, expiry and audience. None if anything is wrong."""
    try:
        head_b64, body_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url(head_b64))
        if header.get("alg") != "HS256":           # never accept 'none' or a different algorithm here
            return None
        expected = hmac.new(secret.encode(), f"{head_b64}.{body_b64}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64url(sig_b64)):
            return None
        claims = json.loads(_b64url(body_b64))
    except Exception:
        return None
    now = time.time() if now is None else now
    if not isinstance(claims.get("exp"), (int, float)) or claims["exp"] <= now:
        return None
    if isinstance(claims.get("nbf"), (int, float)) and claims["nbf"] > now + 5:
        return None
    aud = claims.get("aud")
    if aud is not None and aud != "authenticated" and "authenticated" not in (aud if isinstance(aud, list) else [aud]):
        return None
    sub = claims.get("sub")
    if not sub or not isinstance(sub, str):
        return None
    return AuthUser(id=sub, email=claims.get("email"))


def _token_alg(token: str) -> Optional[str]:
    try:
        return json.loads(_b64url(token.split(".")[0])).get("alg")
    except Exception:
        return None


def verify_remote(token: str) -> Optional[AuthUser]:
    """Ask Supabase's Auth server who this token belongs to. Cached briefly so polling stays cheap."""
    hit = _remote_cache.get(token)
    if hit and hit[0] > time.time():
        return hit[1]
    try:
        r = httpx.get(f"{_url()}/auth/v1/user", timeout=5.0,
                      headers={"apikey": _anon(), "Authorization": f"Bearer {token}"})
    except Exception:
        return None
    if r.status_code != 200:
        return None
    data = r.json()
    if not data.get("id"):
        return None
    user = AuthUser(id=data["id"], email=data.get("email"))
    if len(_remote_cache) > 500:
        _remote_cache.clear()
    _remote_cache[token] = (time.time() + _REMOTE_TTL_S, user)
    return user


def verify_token(token: str) -> Optional[AuthUser]:
    if _secret() and _token_alg(token) == "HS256":
        user = verify_hs256(token, _secret())
        if user:
            return user
        return None            # a bad HS256 signature is final; do not fall through to the network
    if _url() and _anon():
        return verify_remote(token)
    return None


def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency. 401 for a missing or bad token, 503 if auth is not configured at all."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or len(header) < 20:
        raise _unauthorized("Sign in required.")
    if not auth_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Login is not configured on the server. Set SUPABASE_URL and SUPABASE_ANON_KEY (or SUPABASE_JWT_SECRET).")
    user = verify_token(header[len("Bearer "):].strip())
    if not user:
        raise _unauthorized("Your session is invalid or expired. Please sign in again.")
    return user
