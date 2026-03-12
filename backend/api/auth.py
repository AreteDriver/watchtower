"""Sui wallet authentication routes.

Implements wallet-based session management for EVE Frontier (Sui blockchain).
Frontend proves wallet ownership via @mysten/dapp-kit, then registers a session
here. Signature verification is a TODO for production — dapp-kit adapter
already verifies ownership client-side.

Flow:
  1. POST /api/auth/wallet/connect  → create session from Sui wallet address
  2. GET  /api/auth/wallet/me       → return current session + tier info
  3. POST /api/auth/wallet/disconnect → clear session
"""

import hashlib
import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("auth")

router = APIRouter(prefix="/auth")

# Sui addresses: 0x + 64 hex chars (32 bytes)
SUI_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")

# Session TTL: 7 days
SESSION_TTL = 7 * 86400


class WalletConnectRequest(BaseModel):
    wallet_address: str = Field(
        ...,
        pattern=r"^0x[a-fA-F0-9]{64}$",
        description="Sui wallet address (0x + 64 hex chars)",
    )


class WalletConnectResponse(BaseModel):
    session_token: str
    wallet_address: str
    tier: int
    tier_name: str
    is_admin: bool


class WalletMeResponse(BaseModel):
    wallet_address: str
    tier: int
    tier_name: str
    is_admin: bool
    connected_at: int


def _is_admin(wallet_address: str) -> bool:
    """Check if wallet address is in the admin set."""
    return wallet_address.lower() in settings.admin_address_set


@router.post("/wallet/connect")
async def wallet_connect(body: WalletConnectRequest) -> WalletConnectResponse:
    """Register a wallet session.

    Frontend proves ownership via dapp-kit wallet adapter.
    TODO: Add server-side signature verification for production.
    """
    wallet_address = body.wallet_address.lower()

    if not SUI_ADDRESS_RE.match(body.wallet_address):
        raise HTTPException(400, "Invalid Sui wallet address format.")

    # Generate session token
    session_token = secrets.token_urlsafe(32)
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()

    expires_at = int(time.time()) + SESSION_TTL

    db = get_db()

    # Store session
    db.execute(
        """INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at)
           VALUES (?, ?, ?)""",
        (session_hash, wallet_address, expires_at),
    )
    db.commit()

    # Get subscription tier
    from backend.analysis.subscriptions import check_subscription

    sub = check_subscription(db, wallet_address)
    is_admin = _is_admin(wallet_address)

    logger.info(
        "Wallet connected: %s (admin=%s, tier=%d)",
        wallet_address[:16],
        is_admin,
        sub["tier"],
    )

    return WalletConnectResponse(
        session_token=session_token,
        wallet_address=wallet_address,
        tier=sub["tier"],
        tier_name=sub["tier_name"],
        is_admin=is_admin,
    )


def _get_session_wallet(request: Request) -> str | None:
    """Extract wallet address from session header.

    Checks X-Session header, falls back to X-EVE-Session for backwards compat.
    """
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if not session_token:
        return None

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        """SELECT wallet_address FROM wallet_sessions
           WHERE session_hash = ? AND expires_at > ?""",
        (session_hash, int(time.time())),
    ).fetchone()

    if not row:
        return None
    return row["wallet_address"]


@router.get("/wallet/me")
async def wallet_me(request: Request) -> WalletMeResponse:
    """Return wallet info for the current session."""
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if not session_token:
        raise HTTPException(401, "No session. Connect wallet first.")

    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    db = get_db()
    row = db.execute(
        """SELECT wallet_address, created_at FROM wallet_sessions
           WHERE session_hash = ? AND expires_at > ?""",
        (session_hash, int(time.time())),
    ).fetchone()

    if not row:
        raise HTTPException(401, "Session expired. Please reconnect wallet.")

    from backend.analysis.subscriptions import check_subscription

    wallet_address = row["wallet_address"]
    sub = check_subscription(db, wallet_address)

    return WalletMeResponse(
        wallet_address=wallet_address,
        tier=sub["tier"],
        tier_name=sub["tier_name"],
        is_admin=_is_admin(wallet_address),
        connected_at=row["created_at"],
    )


@router.post("/wallet/disconnect")
async def wallet_disconnect(request: Request):
    """Clear wallet session."""
    session_token = request.headers.get("X-Session", request.headers.get("X-EVE-Session", ""))
    if session_token:
        session_hash = hashlib.sha256(session_token.encode()).hexdigest()
        db = get_db()
        db.execute(
            "DELETE FROM wallet_sessions WHERE session_hash = ?",
            (session_hash,),
        )
        db.commit()

    return {"status": "disconnected"}
