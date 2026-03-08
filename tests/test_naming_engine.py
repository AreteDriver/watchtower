"""Tests for naming engine — deterministic title generation."""

import sqlite3

from backend.analysis.naming_engine import (
    _check,
    compute_character_titles,
    compute_gate_titles,
    refresh_all_titles,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --- _check function tests ---


def test_check_gte_suffix_pass():
    assert _check({"kills": 10}, kills_gte=5) is True


def test_check_gte_suffix_fail():
    assert _check({"kills": 3}, kills_gte=5) is False


def test_check_eq_suffix_pass():
    assert _check({"kills": 0}, kills_eq=0) is True


def test_check_eq_suffix_fail():
    assert _check({"kills": 1}, kills_eq=0) is False


def test_check_lte_suffix_pass():
    assert _check({"kills": 2}, kills_lte=5) is True


def test_check_lte_suffix_fail():
    assert _check({"kills": 10}, kills_lte=5) is False


def test_check_lte_suffix_equal():
    assert _check({"kills": 5}, kills_lte=5) is True


def test_check_default_no_suffix_pass():
    """Default (no suffix) behaves as gte."""
    assert _check({"kills": 10}, kills=5) is True


def test_check_default_no_suffix_fail():
    assert _check({"kills": 3}, kills=5) is False


def test_check_default_no_suffix_equal():
    assert _check({"kills": 5}, kills=5) is True


def test_check_missing_key_defaults_zero():
    assert _check({}, kills_gte=1) is False
    assert _check({}, kills_eq=0) is True
    assert _check({}, kills_lte=0) is True
    assert _check({}, kills=1) is False


def test_check_multiple_conditions():
    stats = {"kills": 10, "deaths": 0, "gates": 50}
    assert _check(stats, kills_gte=5, deaths_eq=0, gates_gte=30) is True
    assert _check(stats, kills_gte=5, deaths_eq=1) is False


def test_check_none_value_treated_as_zero():
    """None stat values are treated as 0."""
    assert _check({"kills": None}, kills_gte=1) is False
    assert _check({"kills": None}, kills_eq=0) is True
    assert _check({"kills": None}, kills_lte=0) is True
    assert _check({"kills": None}, kills=1) is False


# --- compute_gate_titles tests ---


def test_compute_gate_titles_missing_entity():
    """Gate not in entities table returns empty."""
    db = _get_test_db()
    result = compute_gate_titles(db, "nonexistent")
    assert result == []


def test_compute_gate_titles_bloodgate():
    """Gate with 10+ nearby killmails earns Bloodgate."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('gate-1', 'gate', 200)"
    )
    # Add gate event to establish solar system link
    db.execute(
        "INSERT INTO gate_events"
        " (gate_id, character_id, solar_system_id,"
        " timestamp)"
        " VALUES ('gate-1', 'pilot-1', 'sys-A', 1000)"
    )
    # Add 12 killmails in that system
    for i in range(12):
        db.execute(
            "INSERT INTO killmails"
            " (killmail_id, solar_system_id, timestamp)"
            " VALUES (?, 'sys-A', ?)",
            (f"km-g-{i}", 1000 + i),
        )
    db.commit()

    titles = compute_gate_titles(db, "gate-1")
    assert "The Bloodgate" in titles


def test_compute_gate_titles_highway():
    """Gate with 1000+ events earns Highway."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, event_count)"
        " VALUES ('gate-hw', 'gate', 1500)"
    )
    db.commit()

    titles = compute_gate_titles(db, "gate-hw")
    assert "The Highway" in titles


# --- compute_character_titles tests ---


def test_compute_character_titles_missing_entity():
    """Character not in entities returns empty."""
    db = _get_test_db()
    result = compute_character_titles(db, "nonexistent")
    assert result == []


def test_compute_character_titles_pathfinder():
    """Character with 50+ gate transits earns Pathfinder."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, gate_count,"
        " event_count, kill_count, death_count)"
        " VALUES ('char-pf', 'character', 55, 60, 1, 1)"
    )
    db.commit()

    titles = compute_character_titles(db, "char-pf")
    assert "The Pathfinder" in titles
    assert "The Wanderer" in titles


def test_compute_character_titles_hunter():
    """Character with 20+ kills earns Hunter."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, kill_count,"
        " event_count, death_count, gate_count)"
        " VALUES ('char-h', 'character', 25, 30, 3, 0)"
    )
    db.commit()

    titles = compute_character_titles(db, "char-h")
    assert "The Hunter" in titles


def test_compute_character_titles_marked():
    """Character with 10+ deaths earns The Marked."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, death_count,"
        " event_count, kill_count, gate_count)"
        " VALUES ('char-m', 'character', 15, 20, 0, 0)"
    )
    db.commit()

    titles = compute_character_titles(db, "char-m")
    assert "The Marked" in titles


# --- refresh_all_titles tests ---


def test_refresh_all_titles_with_gates():
    """Gates with qualifying stats get titles inserted."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('gate-r', 'gate', 1500)"
    )
    db.commit()

    count = refresh_all_titles(db)
    assert count >= 1

    rows = db.execute("SELECT * FROM entity_titles WHERE entity_id = 'gate-r'").fetchall()
    assert len(rows) >= 1
    titles = [r["title"] for r in rows]
    assert "The Highway" in titles


def test_refresh_all_titles_with_characters():
    """Characters with qualifying stats get titles."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, kill_count,"
        " event_count, death_count, gate_count)"
        " VALUES ('char-r', 'character', 25, 30, 3, 0)"
    )
    db.commit()

    count = refresh_all_titles(db)
    assert count >= 1

    rows = db.execute("SELECT * FROM entity_titles WHERE entity_id = 'char-r'").fetchall()
    titles = [r["title"] for r in rows]
    assert "The Hunter" in titles


def test_refresh_all_titles_empty_db():
    """Empty DB returns 0 titles."""
    db = _get_test_db()
    count = refresh_all_titles(db)
    assert count == 0


def test_refresh_all_titles_no_qualifying():
    """Entities that don't meet any thresholds get 0 titles."""
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities"
        " (entity_id, entity_type, event_count,"
        " kill_count, death_count, gate_count)"
        " VALUES ('char-low', 'character', 1, 0, 0, 0)"
    )
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, event_count) VALUES ('gate-low', 'gate', 1)"
    )
    db.commit()

    count = refresh_all_titles(db)
    assert count == 0
