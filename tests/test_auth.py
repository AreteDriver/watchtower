"""Tests for Sui wallet authentication routes."""

import hashlib
import sqlite3
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.db.database import SCHEMA


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def client(test_db):
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
        patch("backend.api.auth.get_db", return_value=test_db),
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.api.routes.check_tier_access"),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from backend.api.app import app
        from backend.api.rate_limit import limiter

        limiter.enabled = False
        yield TestClient(app, raise_server_exceptions=False)
        limiter.enabled = True


# Valid Sui address (0x + 64 hex chars)
VALID_SUI_ADDR = "0x" + "ab" * 32
ADMIN_SUI_ADDR = "0x" + "ff" * 32


def test_wallet_connect_success(client, test_db):
    """Creates session for valid Sui wallet address."""
    r = client.post(
        "/api/auth/wallet/connect",
        json={"wallet_address": VALID_SUI_ADDR},
    )
    assert r.status_code == 200
    data = r.json()
    assert "session_token" in data
    assert data["wallet_address"] == VALID_SUI_ADDR.lower()
    assert data["tier"] == 0
    assert data["tier_name"] == "free"
    assert data["is_admin"] is False

    # Verify session stored in DB
    session_hash = hashlib.sha256(data["session_token"].encode()).hexdigest()
    row = test_db.execute(
        "SELECT * FROM wallet_sessions WHERE session_hash = ?",
        (session_hash,),
    ).fetchone()
    assert row is not None
    assert row["wallet_address"] == VALID_SUI_ADDR.lower()


def test_wallet_connect_invalid_address(client):
    """Rejects invalid wallet address format."""
    # EVM-style address (too short)
    r = client.post(
        "/api/auth/wallet/connect",
        json={"wallet_address": "0x1234567890abcdef1234567890abcdef12345678"},
    )
    assert r.status_code == 422  # Pydantic validation error

    # No 0x prefix
    r = client.post(
        "/api/auth/wallet/connect",
        json={"wallet_address": "a" * 64},
    )
    assert r.status_code == 422


def test_wallet_connect_admin(client):
    """Admin wallet gets is_admin=True."""
    with patch("backend.api.auth.settings") as mock_settings:
        mock_settings.admin_address_set = {ADMIN_SUI_ADDR.lower()}
        r = client.post(
            "/api/auth/wallet/connect",
            json={"wallet_address": ADMIN_SUI_ADDR},
        )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_wallet_me_no_session(client):
    """Returns 401 without session header."""
    r = client.get("/api/auth/wallet/me")
    assert r.status_code == 401


def test_wallet_me_valid_session(client, test_db):
    """Returns wallet info for valid session."""
    # Create session directly
    session_token = "test-valid-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["wallet_address"] == VALID_SUI_ADDR.lower()
    assert data["tier"] == 0


def test_wallet_me_expired_session(client, test_db):
    """Returns 401 for expired session."""
    session_token = "test-expired-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), 1000),  # Long expired
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 401


def test_wallet_me_backwards_compat_header(client, test_db):
    """X-EVE-Session header works as fallback."""
    session_token = "test-eve-compat"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-EVE-Session": session_token},
    )
    assert r.status_code == 200
    assert r.json()["wallet_address"] == VALID_SUI_ADDR.lower()


def test_wallet_disconnect(client, test_db):
    """Clears session on disconnect."""
    session_token = "test-disconnect-session"
    session_hash = hashlib.sha256(session_token.encode()).hexdigest()
    test_db.execute(
        "INSERT INTO wallet_sessions (session_hash, wallet_address, expires_at) VALUES (?, ?, ?)",
        (session_hash, VALID_SUI_ADDR.lower(), int(time.time()) + 3600),
    )
    test_db.commit()

    r = client.post(
        "/api/auth/wallet/disconnect",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "disconnected"

    # Verify session is gone
    row = test_db.execute(
        "SELECT * FROM wallet_sessions WHERE session_hash = ?",
        (session_hash,),
    ).fetchone()
    assert row is None


def test_wallet_disconnect_no_session(client):
    """Disconnect without session returns ok."""
    r = client.post("/api/auth/wallet/disconnect")
    assert r.status_code == 200


def test_admin_bypass_tier_gate(client, test_db):
    """Admin wallets bypass tier checks."""
    from backend.api.tier_gate import is_admin_wallet

    with patch("backend.api.tier_gate.settings") as mock_settings:
        mock_settings.admin_address_set = {ADMIN_SUI_ADDR.lower()}
        assert is_admin_wallet(ADMIN_SUI_ADDR) is True
        assert is_admin_wallet(VALID_SUI_ADDR) is False
        assert is_admin_wallet("") is False


def test_wallet_connect_full_flow(client, test_db):
    """Full flow: connect -> me -> disconnect."""
    # Connect
    r = client.post(
        "/api/auth/wallet/connect",
        json={"wallet_address": VALID_SUI_ADDR},
    )
    assert r.status_code == 200
    session_token = r.json()["session_token"]

    # Me
    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200
    assert r.json()["wallet_address"] == VALID_SUI_ADDR.lower()

    # Disconnect
    r = client.post(
        "/api/auth/wallet/disconnect",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 200

    # Me should fail now
    r = client.get(
        "/api/auth/wallet/me",
        headers={"X-Session": session_token},
    )
    assert r.status_code == 401
