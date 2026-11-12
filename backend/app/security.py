"""Stdlib-only password hashing + HMAC-signed bearer tokens (no card data ever stored)."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from . import config

_RUNTIME_SECRET = config.SECRET_KEY or secrets.token_hex(32)  # ephemeral if unset (dev only)


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, _ = stored.split("$")
        salt = base64.b64decode(salt_b64)
    except Exception:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def make_token(user_id: int, role: str) -> str:
    payload = _b64(json.dumps({"uid": user_id, "role": role, "exp": int(time.time()) + config.TOKEN_TTL_SECONDS}).encode())
    sig = _b64(hmac.new(_RUNTIME_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".")
        expected = _b64(hmac.new(_RUNTIME_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_unb64(payload))
        return data if data["exp"] > time.time() else None
    except Exception:
        return None
