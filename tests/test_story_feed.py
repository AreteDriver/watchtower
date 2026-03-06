"""Tests for story feed generator."""

import sqlite3
import time

from backend.analysis.story_feed import (
    detect_gate_milestones,
    detect_killmail_clusters,
    detect_new_entities,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_detect_killmail_cluster():
    db = _get_test_db()
    now = int(time.time())
    for i in range(5):
        db.execute(
            "INSERT INTO killmails (killmail_id,"
            " solar_system_id, timestamp)"
            f" VALUES ('km{i}', 'sys1', {now - 100 + i})"
        )
    db.commit()

    count = detect_killmail_clusters(db)
    assert count == 1

    stories = db.execute("SELECT * FROM story_feed").fetchall()
    assert len(stories) == 1
    assert "ENGAGEMENT" in stories[0]["headline"]
    assert "5 killmails" in stories[0]["headline"]


def test_no_cluster_below_threshold():
    db = _get_test_db()
    now = int(time.time())
    for i in range(2):
        db.execute(
            "INSERT INTO killmails (killmail_id,"
            " solar_system_id, timestamp)"
            f" VALUES ('km{i}', 'sys1', {now - 100 + i})"
        )
    db.commit()

    count = detect_killmail_clusters(db)
    assert count == 0


def test_detect_new_entity():
    db = _get_test_db()
    now = int(time.time())
    db.execute(
        f"INSERT INTO entities (entity_id, entity_type, display_name, first_seen, event_count) "
        f"VALUES ('char-new', 'character', 'NewPilot', {now - 60}, 1)"
    )
    db.commit()

    count = detect_new_entities(db)
    assert count == 1

    stories = db.execute("SELECT * FROM story_feed").fetchall()
    assert len(stories) == 1
    assert "NEW ENTITY" in stories[0]["headline"]


def test_dedup_prevents_duplicate_stories():
    db = _get_test_db()
    now = int(time.time())
    for i in range(5):
        db.execute(
            "INSERT INTO killmails (killmail_id,"
            " solar_system_id, timestamp)"
            f" VALUES ('km{i}', 'sys1', {now - 100 + i})"
        )
    db.commit()

    count1 = detect_killmail_clusters(db)
    db.commit()
    # Second call should find the same cluster but dedup against existing story
    detect_killmail_clusters(db)
    db.commit()

    stories = db.execute("SELECT COUNT(*) as cnt FROM story_feed").fetchone()
    assert count1 == 1
    assert stories["cnt"] == 1  # Only one story despite two detection runs


def test_gate_milestone():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, event_count) "
        "VALUES ('g1', 'gate', 'Big Gate', 500)"
    )
    db.commit()

    count = detect_gate_milestones(db)
    assert count == 1

    stories = db.execute("SELECT * FROM story_feed").fetchall()
    assert "MILESTONE" in stories[0]["headline"]
