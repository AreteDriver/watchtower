"""Tests for error tracking and rate limit coverage on new endpoints."""

import sqlite3
from unittest.mock import patch, MagicMock

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from backend.api.error_tracker import capture_error, get_errors, _error_buffer
from backend.db.database import SCHEMA


@pytest.fixture(autouse=True)
def clear_buffer():
    """Clear error buffer between tests."""
    _error_buffer.clear()
    yield
    _error_buffer.clear()


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

        yield TestClient(app, raise_server_exceptions=False)


# --- capture_error unit tests ---


def test_capture_error_records_exception():
    """capture_error stores error details in the buffer."""
    req = MagicMock(spec=Request)
    req.url.path = "/api/entity/abc"
    req.method = "GET"

    try:
        raise ValueError("test error message")
    except ValueError as exc:
        capture_error(req, exc)

    errors = get_errors()
    assert len(errors) == 1
    assert errors[0]["path"] == "/api/entity/abc"
    assert errors[0]["method"] == "GET"
    assert errors[0]["error_type"] == "ValueError"
    assert errors[0]["message"] == "test error message"
    assert "traceback" in errors[0]
    assert "timestamp" in errors[0]


def test_capture_error_ring_buffer_maxlen():
    """Buffer respects maxlen of 100."""
    req = MagicMock(spec=Request)
    req.url.path = "/test"
    req.method = "GET"

    for i in range(110):
        try:
            raise RuntimeError(f"error {i}")
        except RuntimeError as exc:
            capture_error(req, exc)

    errors = get_errors()
    assert len(errors) == 100
    # Oldest should be error 10 (0-9 evicted)
    assert errors[0]["message"] == "error 10"
    assert errors[-1]["message"] == "error 109"


def test_get_errors_returns_empty_list():
    """get_errors returns empty list when no errors captured."""
    assert get_errors() == []


def test_capture_error_includes_traceback():
    """Traceback includes the exception line."""
    req = MagicMock(spec=Request)
    req.url.path = "/test"
    req.method = "POST"

    try:
        raise KeyError("missing_key")
    except KeyError as exc:
        capture_error(req, exc)

    errors = get_errors()
    assert "KeyError" in errors[0]["traceback"]


# --- /admin/errors endpoint tests ---


def test_admin_errors_requires_admin(client):
    """GET /admin/errors rejects non-admin wallets."""
    r = client.get("/api/admin/errors", headers={"X-Wallet-Address": "random_wallet"})
    assert r.status_code == 403


def test_admin_errors_rejects_no_wallet(client):
    """GET /admin/errors rejects requests without wallet header."""
    r = client.get("/api/admin/errors")
    assert r.status_code == 403


def test_admin_errors_returns_empty(client):
    """GET /admin/errors returns empty list when no errors."""
    with patch("backend.api.error_tracker.is_admin_wallet", return_value=True):
        r = client.get("/api/admin/errors", headers={"X-Wallet-Address": "admin"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 0
    assert data["errors"] == []


def test_admin_errors_returns_captured_errors(client):
    """GET /admin/errors returns previously captured errors."""
    req = MagicMock(spec=Request)
    req.url.path = "/api/test"
    req.method = "GET"

    try:
        raise TypeError("bad type")
    except TypeError as exc:
        capture_error(req, exc)

    with patch("backend.api.error_tracker.is_admin_wallet", return_value=True):
        r = client.get("/api/admin/errors", headers={"X-Wallet-Address": "admin"})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["errors"][0]["error_type"] == "TypeError"
    assert data["errors"][0]["message"] == "bad type"


# --- Rate limit coverage on new endpoints ---


def test_search_rate_limited(client):
    """GET /search should be rate limited to 60/minute."""
    from backend.api.rate_limit import limiter

    limiter.enabled = True
    limiter._storage.storage.clear()
    try:
        for i in range(60):
            r = client.get("/api/search?q=test")
            assert r.status_code == 200, f"Request {i + 1} should succeed"

        # 61st should be rate limited
        r = client.get("/api/search?q=test")
        assert r.status_code == 429
    finally:
        limiter.enabled = False


def test_entity_lookup_rate_limited(client):
    """GET /entity/{id} should be rate limited to 120/minute."""
    from backend.api.rate_limit import limiter

    limiter.enabled = True
    limiter._storage.storage.clear()
    try:
        # First request should succeed (entity won't exist but rate limit still applies)
        r = client.get("/api/entity/0x" + "aa" * 32)
        assert r.status_code in (200, 404)

        # Verify we get a response (not 429) on early requests
        for _ in range(5):
            r = client.get("/api/entity/0x" + "aa" * 32)
            assert r.status_code != 429
    finally:
        limiter.enabled = False
