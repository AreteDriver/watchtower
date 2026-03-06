"""Tests for FastAPI routes."""

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
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 0, 0, 0, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 3, 1, 10, 1000, 5000)"
    )
    conn.execute(
        "INSERT INTO story_feed (event_type, headline, body, entity_ids, severity, timestamp) "
        "VALUES ('engagement', 'Test Battle', 'Details', '[\"gate-001\"]', 'warning', 1000)"
    )
    conn.commit()
    return conn


@pytest.fixture
def client(test_db):
    # Patch at the source module so all importers see the mock
    with (
        patch("backend.db.database.get_db", return_value=test_db),
        patch("backend.api.routes.get_db", return_value=test_db),
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.ingestion.poller.run_poller"),
    ):
        from backend.api.app import app

        yield TestClient(app, raise_server_exceptions=False)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "tables" in data


def test_get_entity(client):
    r = client.get("/api/entity/gate-001")
    assert r.status_code == 200
    data = r.json()
    assert data["entity_id"] == "gate-001"
    assert data["display_name"] == "Alpha Gate"


def test_get_entity_not_found(client):
    r = client.get("/api/entity/nonexistent")
    assert r.status_code == 404


def test_list_entities(client):
    r = client.get("/api/entities")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert len(data["entities"]) == 2


def test_list_entities_by_type(client):
    r = client.get("/api/entities?entity_type=gate")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1


def test_story_feed(client):
    r = client.get("/api/feed")
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["headline"] == "Test Battle"


def test_search(client):
    r = client.get("/api/search?q=Alpha")
    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 1
    assert data["results"][0]["display_name"] == "Alpha Gate"


def test_search_min_length(client):
    r = client.get("/api/search?q=A")
    assert r.status_code == 422


def test_titles_empty(client):
    r = client.get("/api/titles")
    assert r.status_code == 200
    data = r.json()
    assert data["titles"] == []
