"""Tests for database initialization and schema."""

import sqlite3

from backend.db import database


def _get_test_db():
    """Create an in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(database.SCHEMA)
    return conn


def test_schema_creates_all_tables():
    db = _get_test_db()
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {t["name"] for t in tables}

    expected = {
        "killmails",
        "gate_events",
        "storage_snapshots",
        "entities",
        "entity_titles",
        "watches",
        "narrative_cache",
        "story_feed",
    }
    assert expected.issubset(table_names)


def test_killmail_unique_constraint():
    db = _get_test_db()
    db.execute("INSERT INTO killmails (killmail_id, timestamp) VALUES ('km1', 1000)")
    db.execute("INSERT OR IGNORE INTO killmails (killmail_id, timestamp) VALUES ('km1', 2000)")
    row = db.execute("SELECT COUNT(*) as cnt FROM killmails").fetchone()
    assert row["cnt"] == 1


def test_entity_upsert():
    db = _get_test_db()
    db.execute(
        """INSERT INTO entities (entity_id, entity_type, event_count)
           VALUES ('e1', 'character', 5)"""
    )
    db.execute(
        """INSERT INTO entities (entity_id, entity_type, event_count)
           VALUES ('e1', 'character', 10)
           ON CONFLICT(entity_id) DO UPDATE SET event_count = excluded.event_count"""
    )
    row = db.execute("SELECT event_count FROM entities WHERE entity_id = 'e1'").fetchone()
    assert row["event_count"] == 10


def test_entity_title_unique_constraint():
    db = _get_test_db()
    db.execute("INSERT INTO entities (entity_id, entity_type) VALUES ('g1', 'gate')")
    db.execute(
        """INSERT INTO entity_titles (entity_id, title, title_type)
           VALUES ('g1', 'The Meatgrinder', 'earned')"""
    )
    db.execute(
        """INSERT OR IGNORE INTO entity_titles (entity_id, title, title_type)
           VALUES ('g1', 'The Meatgrinder', 'earned')"""
    )
    row = db.execute("SELECT COUNT(*) as cnt FROM entity_titles").fetchone()
    assert row["cnt"] == 1


def test_indexes_exist():
    db = _get_test_db()
    indexes = db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
    ).fetchall()
    index_names = {i["name"] for i in indexes}
    assert "idx_killmails_timestamp" in index_names
    assert "idx_gate_events_timestamp" in index_names
    assert "idx_entities_type" in index_names
