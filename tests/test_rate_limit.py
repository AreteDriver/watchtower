"""Tests for rate limiting."""

import sqlite3
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
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.api.routes.check_tier_access"),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from backend.api.app import app
        from backend.api.rate_limit import limiter

        # Enable rate limiting for these tests
        limiter.enabled = True
        # Clear rate limit storage between tests
        limiter._storage.storage.clear()
        yield TestClient(app, raise_server_exceptions=False)
        limiter.enabled = False


def test_subscribe_rate_limit(client):
    """POST /subscribe should be rate limited to 5/minute."""
    wallet = "0x1234567890abcdef1234567890abcdef12345678"
    for i in range(5):
        r = client.post("/api/subscribe", json={"wallet_address": wallet, "tier": 1})
        assert r.status_code == 200, f"Request {i + 1} should succeed"

    # 6th request should be rate limited
    r = client.post("/api/subscribe", json={"wallet_address": wallet, "tier": 1})
    assert r.status_code == 429


def test_health_not_rate_limited(client):
    """GET /health should not be rate limited."""
    for _ in range(20):
        r = client.get("/api/health")
        assert r.status_code == 200
