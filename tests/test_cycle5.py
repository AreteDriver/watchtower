"""Tests for Cycle 5 endpoints — orbital zones, scans, clones, crowns."""

import sqlite3
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.cycle5 import CYCLE_NUMBER, CYCLE_RESET_EPOCH, _threat_level
from backend.db.database import SCHEMA


def _seed_c5_data(db):
    """Seed test data for all C5 tables."""
    now = int(time.time())

    db.execute(
        """INSERT INTO orbital_zones (zone_id, name, solar_system_id, feral_ai_tier, last_scanned)
           VALUES (?, ?, ?, ?, ?)""",
        ("zone-001", "Alpha Sector", "sys-1", 2, now - 60),
    )
    db.execute(
        """INSERT INTO orbital_zones (zone_id, name, solar_system_id, feral_ai_tier, last_scanned)
           VALUES (?, ?, ?, ?, ?)""",
        ("zone-002", "Beta Sector", "sys-2", 0, now - 2000),
    )

    db.execute(
        """INSERT INTO feral_ai_events
           (zone_id, event_type, old_tier, new_tier, severity, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("zone-001", "evolution", 1, 2, "warning", now - 120),
    )

    db.execute(
        """INSERT INTO scans (scan_id, zone_id, scanner_id, scanner_name, result_type, scanned_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("scan-001", "zone-001", "char-1", "Pilot Alpha", "CLEAR", now - 60),
    )
    db.execute(
        """INSERT INTO scans (scan_id, zone_id, scanner_id, scanner_name, result_type, scanned_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("scan-002", "zone-002", "char-2", "Pilot Beta", "HOSTILE", now - 30),
    )

    db.execute(
        """INSERT INTO clones
           (clone_id, owner_id, owner_name, blueprint_id, status, manufactured_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("clone-001", "char-1", "Pilot Alpha", "bp-001", "active", now - 3600),
    )
    db.execute(
        """INSERT INTO clones
           (clone_id, owner_id, owner_name, blueprint_id, status, manufactured_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("clone-002", "char-1", "Pilot Alpha", "bp-001", "manufacturing", now),
    )

    db.execute(
        """INSERT INTO clone_blueprints (blueprint_id, name, tier, manufacture_time_sec)
           VALUES (?, ?, ?, ?)""",
        ("bp-001", "Standard Clone", 1, 3600),
    )

    db.execute(
        """INSERT INTO crowns (crown_id, character_id, character_name, crown_type, equipped_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("crown-001", "char-1", "Pilot Alpha", "warrior", now - 7200),
    )
    db.execute(
        """INSERT INTO crowns (crown_id, character_id, character_name, crown_type, equipped_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("crown-002", "char-2", "Pilot Beta", "merchant", now - 3600),
    )

    db.commit()


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _seed_c5_data(conn)
    return conn


@pytest.fixture
def client(test_db):
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.cycle5.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
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


class TestThreatLevel:
    def test_dormant(self):
        assert _threat_level(0) == "DORMANT"

    def test_active(self):
        assert _threat_level(1) == "ACTIVE"

    def test_evolved(self):
        assert _threat_level(2) == "EVOLVED"

    def test_critical(self):
        assert _threat_level(3) == "CRITICAL"

    def test_unknown(self):
        assert _threat_level(99) == "UNKNOWN"


class TestCycleEndpoint:
    def test_cycle_info(self, client):
        resp = client.get("/api/cycle")
        assert resp.status_code == 200
        body = resp.json()
        assert body["cycle"] == CYCLE_NUMBER
        assert body["reset_at"] == CYCLE_RESET_EPOCH
        assert body["data"]["number"] == 5
        assert body["data"]["name"] == "Shroud of Fear"
        assert "days_elapsed" in body["data"]


class TestOrbitalZones:
    def test_list_all(self, client):
        resp = client.get("/api/orbital-zones")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["feral_ai_tier"] >= data[1]["feral_ai_tier"]

    def test_filter_by_threat(self, client):
        resp = client.get("/api/orbital-zones?threat_level=EVOLVED")
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["zone_id"] == "zone-001"

    def test_filter_no_match(self, client):
        resp = client.get("/api/orbital-zones?threat_level=CRITICAL")
        data = resp.json()["data"]
        assert len(data) == 0

    def test_stale_flag(self, client):
        resp = client.get("/api/orbital-zones")
        data = resp.json()["data"]
        beta = next(z for z in data if z["zone_id"] == "zone-002")
        assert beta["stale"] is True

    def test_zone_history(self, client):
        resp = client.get("/api/orbital-zones/zone-001/history")
        assert resp.status_code == 200
        events = resp.json()["data"]
        assert len(events) == 1
        assert events[0]["old_threat"] == "ACTIVE"
        assert events[0]["new_threat"] == "EVOLVED"

    def test_zone_history_empty(self, client):
        resp = client.get("/api/orbital-zones/zone-999/history")
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestScans:
    def test_list_all(self, client):
        resp = client.get("/api/scans")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_filter_by_zone(self, client):
        resp = client.get("/api/scans?zone_id=zone-001")
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["zone_id"] == "zone-001"

    def test_filter_by_result_type(self, client):
        resp = client.get("/api/scans?result_type=HOSTILE")
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["result_type"] == "HOSTILE"

    def test_scan_feed(self, client):
        resp = client.get("/api/scans/feed")
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) == 2
        assert "zone_hostile_recent" in items[0]


class TestClones:
    def test_list_active(self, client):
        resp = client.get("/api/clones")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["status"] == "active"

    def test_queue(self, client):
        resp = client.get("/api/clones/queue")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["blueprint_name"] == "Standard Clone"


class TestCrowns:
    def test_list_all(self, client):
        resp = client.get("/api/crowns")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 2

    def test_roster(self, client):
        resp = client.get("/api/crowns/roster")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "distribution" in data
        assert data["crowned"] == 2
        assert len(data["distribution"]) == 2
