"""Tests for naming engine."""

import sqlite3

from backend.analysis.naming_engine import (
    compute_character_titles,
    compute_gate_titles,
    refresh_all_titles,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def test_gate_earns_meatgrinder():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('g1', 'gate', 200)"
    )
    # Seed killmails in same system
    for i in range(25):
        db.execute(
            "INSERT INTO killmails (killmail_id,"
            " solar_system_id, timestamp)"
            f" VALUES ('km{i}', 'sys1', {1000 + i})"
        )
    db.execute(
        "INSERT INTO gate_events (gate_id, solar_system_id,"
        " character_id, timestamp)"
        " VALUES ('g1', 'sys1', 'c1', 1000)"
    )
    db.commit()

    titles = compute_gate_titles(db, "g1")
    assert "The Meatgrinder" in titles


def test_gate_earns_highway():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('g2', 'gate', 1500)"
    )
    db.execute(
        "INSERT INTO gate_events (gate_id, solar_system_id,"
        " character_id, timestamp)"
        " VALUES ('g2', 'sys2', 'c1', 1000)"
    )
    db.commit()

    titles = compute_gate_titles(db, "g2")
    assert "The Highway" in titles


def test_character_earns_pathfinder():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type,"
        " gate_count, event_count, kill_count, death_count) "
        "VALUES ('c1', 'character', 60, 100, 0, 0)"
    )
    db.commit()

    titles = compute_character_titles(db, "c1")
    assert "The Pathfinder" in titles


def test_character_earns_ghost():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type,"
        " gate_count, event_count, kill_count, death_count) "
        "VALUES ('c2', 'character', 40, 80, 0, 0)"
    )
    db.commit()

    titles = compute_character_titles(db, "c2")
    assert "The Ghost" in titles


def test_refresh_all_titles():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type,"
        " gate_count, event_count, kill_count, death_count) "
        "VALUES ('c3', 'character', 60, 100, 25, 0)"
    )
    db.commit()

    count = refresh_all_titles(db)
    assert count > 0

    titles = db.execute("SELECT title FROM entity_titles WHERE entity_id = 'c3'").fetchall()
    title_names = [t["title"] for t in titles]
    assert "The Pathfinder" in title_names
    assert "The Hunter" in title_names
