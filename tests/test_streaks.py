"""Tests for streak & momentum tracker."""

import json
import sqlite3
import time

import pytest

from backend.analysis.streaks import _get_kill_timestamps, compute_streaks, get_hot_streaks
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    now = int(time.time())

    # Hunter with active streak: 8 kills over 5 days
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count)"
        " VALUES ('hunter-1', 'character', 'ActiveHunter', 8)"
    )
    for i in range(8):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-h1-{i}",
                f"prey-{i}",
                json.dumps([{"address": "hunter-1"}]),
                "sys-A",
                now - 86400 * 5 + i * 86400,  # one kill per day for 5 days
            ),
        )

    # Dormant hunter: kills from 30 days ago
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count)"
        " VALUES ('hunter-2', 'character', 'DormantHunter', 3)"
    )
    for i in range(3):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-h2-{i}",
                f"prey-d-{i}",
                json.dumps([{"address": "hunter-2"}]),
                "sys-B",
                now - 86400 * 30 + i * 3600,
            ),
        )

    # Entity with broken streak: kills, gap, then more kills
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count)"
        " VALUES ('hunter-3', 'character', 'StreakBreaker', 6)"
    )
    # First streak: 3 kills close together
    for i in range(3):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-h3-a-{i}",
                f"prey-s-{i}",
                json.dumps([{"address": "hunter-3"}]),
                "sys-C",
                now - 86400 * 60 + i * 3600,  # 60 days ago
            ),
        )
    # Second streak: 3 kills recently (after a 50-day gap > STREAK_WINDOW)
    for i in range(3):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-h3-b-{i}",
                f"prey-s2-{i}",
                json.dumps([{"address": "hunter-3"}]),
                "sys-C",
                now - 86400 * 2 + i * 3600,  # 2 days ago
            ),
        )

    # No-kill entity
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count)"
        " VALUES ('pacifist', 'character', 'Peaceful', 0)"
    )

    conn.commit()
    return conn


def test_active_streak(db):
    info = compute_streaks(db, "hunter-1")
    assert info.current_streak == 8
    assert info.longest_streak == 8
    assert info.status in ("active", "hot")
    assert info.kills_7d > 0


def test_dormant_hunter(db):
    info = compute_streaks(db, "hunter-2")
    assert info.current_streak == 0  # no recent kills
    assert info.longest_streak == 3
    assert info.status == "dormant"


def test_broken_streak(db):
    info = compute_streaks(db, "hunter-3")
    # Two separate streaks of 3
    assert info.longest_streak == 3
    assert info.current_streak == 3  # recent streak still active


def test_no_kills(db):
    info = compute_streaks(db, "pacifist")
    assert info.current_streak == 0
    assert info.longest_streak == 0
    assert info.status == "inactive"
    assert info.kills_7d == 0


def test_nonexistent_entity(db):
    info = compute_streaks(db, "does-not-exist")
    assert info.current_streak == 0
    assert info.longest_streak == 0


def test_to_dict(db):
    info = compute_streaks(db, "hunter-1")
    d = info.to_dict()
    assert "current_streak" in d
    assert "longest_streak" in d
    assert "status" in d
    assert "kills_7d" in d
    assert "avg_kills_per_week" in d
    assert isinstance(d["avg_kills_per_week"], float)


def test_hot_streaks(db):
    streaks = get_hot_streaks(db)
    assert len(streaks) > 0
    # Should be sorted by current_streak desc
    if len(streaks) >= 2:
        assert streaks[0]["current_streak"] >= streaks[1]["current_streak"]


def test_get_kill_timestamps(db):
    timestamps = _get_kill_timestamps(db, "hunter-1")
    assert len(timestamps) == 8
    # Should be sorted ascending
    assert timestamps == sorted(timestamps)


def test_get_kill_timestamps_no_false_match(db):
    """LIKE match shouldn't false-match similar IDs."""
    timestamps = _get_kill_timestamps(db, "hunter-")
    assert len(timestamps) == 0


def test_kills_30d(db):
    info = compute_streaks(db, "hunter-1")
    assert info.kills_30d >= info.kills_7d


def test_malformed_json(db):
    """Malformed attacker JSON should be skipped."""
    db.execute(
        "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
        " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("km-bad", "prey-x", "not-json", "sys-Z", int(time.time())),
    )
    db.commit()
    timestamps = _get_kill_timestamps(db, "hunter-1")
    assert len(timestamps) == 8  # unchanged
