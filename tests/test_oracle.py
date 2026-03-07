"""Tests for Oracle watch evaluation engine."""

import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.analysis.oracle import check_watches
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _insert_watch(db, watch_type, target_id, conditions="{}"):
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, "
        "webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        (
            "user1",
            watch_type,
            target_id,
            conditions,
            "https://discord.com/api/webhooks/test",
        ),
    )
    db.commit()


@pytest.mark.asyncio
async def test_entity_movement_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "entity_movement",
        "pilot-1",
        '{"lookback_seconds": 600}',
    )
    db.execute(
        "INSERT INTO gate_events "
        "(gate_id, gate_name, character_id, "
        "solar_system_id, timestamp) "
        f"VALUES ('g1', 'Test Gate', 'pilot-1', 's1', {now - 10})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    mock_webhook.assert_called_once()
    title = mock_webhook.call_args[0][1]
    assert "MOVEMENT" in title


@pytest.mark.asyncio
async def test_gate_traffic_spike_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "gate_traffic_spike",
        "g1",
        '{"threshold": 3, "lookback_seconds": 3600}',
    )
    for i in range(5):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'c{i}', 's1', {now - 10 + i})"
        )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "TRAFFIC SPIKE" in title


@pytest.mark.asyncio
async def test_killmail_proximity_triggers():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "killmail_proximity",
        "sys-1",
        '{"lookback_seconds": 1800}',
    )
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 60})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "KILLMAIL" in title


@pytest.mark.asyncio
async def test_cooldown_prevents_refire():
    db = _get_test_db()
    now = int(time.time())
    _insert_watch(
        db,
        "killmail_proximity",
        "sys-1",
        '{"lookback_seconds": 1800}',
    )
    # Mark as recently triggered
    db.execute(
        "UPDATE watches SET last_triggered = ?",
        (now - 60,),
    )
    db.execute(
        "INSERT INTO killmails "
        "(killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 10})"
    )
    db.commit()

    with (
        patch(
            "backend.analysis.oracle.get_db",
            return_value=db,
        ),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 0
    mock_webhook.assert_not_called()


@pytest.mark.asyncio
async def test_no_watches_returns_zero():
    db = _get_test_db()

    with patch(
        "backend.analysis.oracle.get_db",
        return_value=db,
    ):
        fired = await check_watches()

    assert fired == 0


@pytest.mark.asyncio
async def test_hostile_sighting_triggers():
    db = _get_test_db()
    now = int(time.time())
    import json

    conditions = json.dumps(
        {
            "corps": ["evil-corp"],
            "gates": ["g1"],
            "lookback_seconds": 300,
        }
    )
    _insert_watch(db, "hostile_sighting", "watch-hostiles", conditions)
    db.execute(
        "INSERT INTO gate_events "
        "(gate_id, gate_name, character_id, corp_id, "
        "solar_system_id, timestamp) "
        f"VALUES ('g1', 'War Gate', 'bad-pilot', 'evil-corp', 's1', {now - 10})"
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        fired = await check_watches()

    assert fired == 1
    title = mock_webhook.call_args[0][1]
    assert "HOSTILE" in title


@pytest.mark.asyncio
async def test_watch_no_webhook_uses_default():
    """Watch with empty webhook_url falls back to settings default."""
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("user1", "killmail_proximity", "sys-1", '{"lookback_seconds": 1800}', ""),
    )
    db.execute(
        "INSERT INTO killmails (killmail_id, solar_system_id, timestamp) "
        f"VALUES ('km1', 'sys-1', {now - 60})"
    )
    db.commit()

    with (
        patch("backend.analysis.oracle.get_db", return_value=db),
        patch("backend.analysis.oracle.settings") as mock_settings,
        patch(
            "backend.analysis.oracle.fire_webhook",
            new_callable=AsyncMock,
        ) as mock_webhook,
    ):
        mock_settings.DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/default"
        fired = await check_watches()

    assert fired == 1
    # Should use the default webhook URL
    mock_webhook.assert_called_once()
    assert mock_webhook.call_args[0][0] == "https://discord.com/api/webhooks/default"


@pytest.mark.asyncio
async def test_invalid_conditions_json_skipped():
    """Watch with invalid JSON conditions is silently skipped."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO watches "
        "(user_id, watch_type, target_id, conditions, webhook_url, active) "
        "VALUES (?, ?, ?, ?, ?, 1)",
        ("user1", "entity_movement", "pilot-1", "not-valid-json", "https://example.com"),
    )
    db.commit()

    with patch("backend.analysis.oracle.get_db", return_value=db):
        fired = await check_watches()

    assert fired == 0
