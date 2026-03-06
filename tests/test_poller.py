"""Tests for World API poller."""

import sqlite3
import time

import pytest
import respx
from httpx import Response

from backend.db.database import SCHEMA
from backend.ingestion.poller import (
    _ingest_gate_events,
    _ingest_killmails,
    _update_entities,
    poll_endpoint,
)


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.mark.asyncio
@respx.mock
async def test_poll_endpoint_returns_list():
    import httpx

    respx.get("http://test/killmails").mock(return_value=Response(200, json=[{"id": "km1"}]))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                type(
                    "S",
                    (),
                    {
                        "WORLD_API_BASE": "http://test",
                        "POLL_TIMEOUT_SECONDS": 5,
                    },
                )(),
            )
            result = await poll_endpoint(client, "killmails")
    assert result == [{"id": "km1"}]


@pytest.mark.asyncio
@respx.mock
async def test_poll_endpoint_returns_empty_on_error():
    import httpx

    respx.get("http://test/bad").mock(return_value=Response(500))
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                type(
                    "S",
                    (),
                    {
                        "WORLD_API_BASE": "http://test",
                        "POLL_TIMEOUT_SECONDS": 5,
                    },
                )(),
            )
            result = await poll_endpoint(client, "bad")
    assert result == []


@pytest.mark.asyncio
@respx.mock
async def test_poll_endpoint_unwraps_data_key():
    import httpx

    respx.get("http://test/wrapped").mock(
        return_value=Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})
    )
    async with httpx.AsyncClient() as client:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "backend.ingestion.poller.settings",
                type(
                    "S",
                    (),
                    {
                        "WORLD_API_BASE": "http://test",
                        "POLL_TIMEOUT_SECONDS": 5,
                    },
                )(),
            )
            result = await poll_endpoint(client, "wrapped")
    assert len(result) == 2


def test_ingest_killmails():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {
            "id": "km-001",
            "victim": {
                "characterId": "char-v1",
                "corporationId": "corp-v1",
            },
            "attackers": [
                {"corporationId": "corp-a1"},
            ],
            "solarSystemId": "sys-1",
            "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            "timestamp": now,
        }
    ]
    count = _ingest_killmails(db, raw)
    assert count == 1

    row = db.execute("SELECT * FROM killmails WHERE killmail_id = 'km-001'").fetchone()
    assert row is not None
    assert row["victim_character_id"] == "char-v1"
    assert row["x"] == 1.0


def test_ingest_killmails_skips_no_id():
    db = _get_test_db()
    count = _ingest_killmails(db, [{"noId": True}])
    assert count == 0


def test_ingest_killmails_dedup():
    db = _get_test_db()
    raw = [{"id": "km-dup", "timestamp": 1000}]
    _ingest_killmails(db, raw)
    count = _ingest_killmails(db, raw)
    assert count == 1  # INSERT OR IGNORE counts as success

    total = db.execute("SELECT COUNT(*) as cnt FROM killmails").fetchone()
    assert total["cnt"] == 1


def test_ingest_gate_events():
    db = _get_test_db()
    now = int(time.time())
    raw = [
        {
            "id": "gate-001",
            "name": "Alpha Gate",
            "characterId": "char-1",
            "corporationId": "corp-1",
            "solarSystemId": "sys-1",
            "direction": "enter",
            "timestamp": now,
        }
    ]
    count = _ingest_gate_events(db, raw)
    assert count == 1

    row = db.execute("SELECT * FROM gate_events WHERE gate_id = 'gate-001'").fetchone()
    assert row is not None
    assert row["gate_name"] == "Alpha Gate"


def test_ingest_gate_events_skips_no_id():
    db = _get_test_db()
    count = _ingest_gate_events(db, [{"noId": True}])
    assert count == 0


def test_update_entities_from_killmails():
    db = _get_test_db()
    now = int(time.time())
    for i in range(3):
        db.execute(
            "INSERT INTO killmails "
            "(killmail_id, victim_character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('km{i}', 'victim-1', 'sys-1', {now + i})"
        )
    db.commit()

    _update_entities(db)
    db.commit()

    entity = db.execute("SELECT * FROM entities WHERE entity_id = 'victim-1'").fetchone()
    assert entity is not None
    assert entity["entity_type"] == "character"
    assert entity["death_count"] == 3


def test_update_entities_from_gate_events():
    db = _get_test_db()
    now = int(time.time())
    for i in range(5):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, gate_name, character_id, "
            "solar_system_id, timestamp) "
            "VALUES "
            f"('g1', 'Gate One', 'pilot-1', 'sys-1', {now + i})"
        )
    db.commit()

    _update_entities(db)
    db.commit()

    pilot = db.execute("SELECT * FROM entities WHERE entity_id = 'pilot-1'").fetchone()
    assert pilot is not None
    assert pilot["gate_count"] == 5

    gate = db.execute("SELECT * FROM entities WHERE entity_id = 'g1'").fetchone()
    assert gate is not None
    assert gate["entity_type"] == "gate"
    assert gate["display_name"] == "Gate One"
