"""JWT authentication and role-based access control.

Phase 4: hardcoded users (Vishnu/Siva/Vyas) with JWT tokens.
Phase 6: replace with DB-backed user store.

Roles:
  admin   — all clients, all actions, Tier 1/2/3
  manager — assigned clients only, Tier 1/2 actions
  viewer  — assigned clients only, read-only (Tier 1 only)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8   # 8-hour sessions

# sha256_crypt avoids bcrypt's 72-byte self-test bug in newer bcrypt versions
_pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


# ── Hardcoded users (Phase 6 → DB) ────────────────────────────────────────────
# Pre-computed sha256_crypt hashes (avoid import-time hashing).
# Regenerate with: python -c "from passlib.context import CryptContext; c=CryptContext(schemes=['sha256_crypt']); print(c.hash('yourpassword'))"
# Default passwords: vishnu→admin123  siva→manager123  vyas→viewer123

_USERS: dict[str, dict] = {
    "vishnu": {
        "username": "vishnu",
        "hashed_password": "$5$rounds=535000$2m7fjpVc/IhW7gHL$28IkN3S9VEerYAS2zNI9c/DUA8TMSpVU8OSwgegBrL1",
        "role": "admin",
        "client_ids": ["*"],           # * means all clients
    },
    "siva": {
        "username": "siva",
        "hashed_password": "$5$rounds=535000$0fqWH7P777034NIr$W4e3fibOcx6gseT0d4L9eojMPIsKXv94wU4a9Q9Yrx9",
        "role": "manager",
        "client_ids": ["tickets99"],
    },
    "vyas": {
        "username": "vyas",
        "hashed_password": "$5$rounds=535000$md7H0GEwI64AmA5q$IS3rQ3m3rmJc1s06x4gE1i73NkhMTx4YGYQUwyVI2A1",
        "role": "viewer",
        "client_ids": ["tickets99"],
    },
}


# ── Token operations ───────────────────────────────────────────────────────────


def create_access_token(username: str, role: str, client_ids: list[str], secret_key: str) -> str:
    """Create a signed JWT for the given user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "client_ids": client_ids,
        "exp": expire,
    }
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def decode_token(token: str, secret_key: str) -> dict:
    """Decode and verify a JWT. Raises JWTError on failure."""
    return jwt.decode(token, secret_key, algorithms=[ALGORITHM])


# ── User operations ────────────────────────────────────────────────────────────


def get_user(username: str) -> Optional[dict]:
    return _USERS.get(username.lower())


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return user dict if credentials are valid, else None."""
    user = get_user(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user


# ── Role checks ────────────────────────────────────────────────────────────────


def can_access_client(user: dict, client_id: str) -> bool:
    """True if user is allowed to see/act on this client."""
    return "*" in user["client_ids"] or client_id in user["client_ids"]


def can_approve(user: dict) -> bool:
    """True if user can approve Tier 2 actions."""
    return user["role"] in ("admin", "manager")


def can_approve_tier3(user: dict) -> bool:
    """True if user can approve Tier 3 (restricted) actions."""
    return user["role"] == "admin"


def is_admin(user: dict) -> bool:
    return user["role"] == "admin"
