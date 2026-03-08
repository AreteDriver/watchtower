"""Tests for subscription tier gating."""

import sqlite3
import time
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.subscriptions import _cache as sub_cache
from backend.api.tier_gate import check_tier_access
from backend.db.database import SCHEMA

_INSERT_SUB = (
    "INSERT INTO watcher_subscriptions"
    " (wallet_address, tier, expires_at, created_at)"
    " VALUES (?, ?, ?, ?)"
)


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture(autouse=True)
def clear_sub_cache():
    """Clear subscription cache between tests."""
    sub_cache.clear()
    yield
    sub_cache.clear()


def _make_request(wallet: str = "") -> MagicMock:
    req = MagicMock()
    req.headers = {"X-Wallet-Address": wallet} if wallet else {}
    return req


def test_ungated_route_passes(test_db):
    """Non-gated routes should pass without any checks."""
    req = _make_request()
    check_tier_access(req, "health")


def test_gated_route_no_wallet(test_db):
    """Gated route with no wallet header should raise 403."""
    req = _make_request()
    with pytest.raises(Exception) as exc:
        check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403
    assert "Wallet address required" in str(exc.value.detail)


def test_gated_route_no_subscription(test_db):
    """Gated route with wallet but no subscription should raise 403."""
    req = _make_request("0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403
    assert "Insufficient tier" in str(exc.value.detail)


def test_gated_route_sufficient_tier(test_db):
    """Gated route with sufficient tier should pass."""
    wallet = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    now = int(time.time())
    test_db.execute(
        _INSERT_SUB,
        (wallet, 1, now + 86400, now),
    )
    test_db.commit()

    req = _make_request(wallet)
    with patch("backend.db.database.get_db", return_value=test_db):
        check_tier_access(req, "get_entity_fingerprint")


def test_gated_route_insufficient_tier(test_db):
    """Scout trying to access Spymaster endpoint should raise 403."""
    wallet = "0xcccccccccccccccccccccccccccccccccccccccc"
    now = int(time.time())
    test_db.execute(
        _INSERT_SUB,
        (wallet, 1, now + 86400, now),
    )
    test_db.commit()

    req = _make_request(wallet)
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_kill_graph")
    assert exc.value.status_code == 403
    assert "spymaster" in str(exc.value.detail).lower()


def test_gated_route_expired_subscription(test_db):
    """Expired subscription should raise 403."""
    wallet = "0xdddddddddddddddddddddddddddddddddddddd"
    test_db.execute(
        _INSERT_SUB,
        (wallet, 3, 1000, 500),
    )
    test_db.commit()

    req = _make_request(wallet)
    with patch("backend.db.database.get_db", return_value=test_db):
        with pytest.raises(Exception) as exc:
            check_tier_access(req, "get_entity_fingerprint")
    assert exc.value.status_code == 403


def test_oracle_can_access_scout(test_db):
    """Higher tier should access lower tier endpoints."""
    wallet = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    now = int(time.time())
    test_db.execute(
        _INSERT_SUB,
        (wallet, 2, now + 86400, now),
    )
    test_db.commit()

    req = _make_request(wallet)
    with patch("backend.db.database.get_db", return_value=test_db):
        check_tier_access(req, "get_entity_fingerprint")


def test_spymaster_can_access_all(test_db):
    """Spymaster should access all gated endpoints."""
    wallet = "0xffffffffffffffffffffffffffffffffffffffff"
    now = int(time.time())
    test_db.execute(
        _INSERT_SUB,
        (wallet, 3, now + 86400, now),
    )
    test_db.commit()

    req = _make_request(wallet)
    with patch("backend.db.database.get_db", return_value=test_db):
        for route in ["get_entity_fingerprint", "get_entity_narrative", "get_kill_graph"]:
            check_tier_access(req, route)
