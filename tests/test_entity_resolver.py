"""Tests for entity resolver."""

import sqlite3

from backend.analysis.entity_resolver import resolve_entity
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_gate(db):
    """Seed a gate with some events."""
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-001', 'gate', 'Alpha Gate',"
        " 150, 0, 0, 0, 1000, 5000)"
    )
    for i in range(20):
        db.execute(
            "INSERT INTO gate_events (gate_id, gate_name,"
            " character_id, corp_id, solar_system_id, timestamp)"
            f" VALUES ('gate-001', 'Alpha Gate',"
            f" 'char-{i % 5}', 'corp-{i % 3}',"
            f" 'sys-001', {1000 + i * 100})"
        )
    db.commit()


def _seed_character(db):
    """Seed a character with events."""
    db.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-001', 'character', 'TestPilot',"
        " 50, 3, 1, 10, 1000, 5000)"
    )
    for i in range(10):
        db.execute(
            "INSERT INTO gate_events (gate_id, gate_name,"
            " character_id, corp_id, solar_system_id, timestamp)"
            f" VALUES ('gate-{i % 3}', 'Gate {i % 3}',"
            f" 'char-001', 'corp-001',"
            f" 'sys-001', {1000 + i * 100})"
        )
    db.commit()


def test_resolve_gate():
    db = _get_test_db()
    _seed_gate(db)
    dossier = resolve_entity(db, "gate-001")
    assert dossier is not None
    assert dossier.entity_type == "gate"
    assert dossier.display_name == "Alpha Gate"
    assert dossier.unique_pilots == 5
    assert len(dossier.associated_corps) > 0


def test_resolve_character():
    db = _get_test_db()
    _seed_character(db)
    dossier = resolve_entity(db, "char-001")
    assert dossier is not None
    assert dossier.entity_type == "character"
    assert dossier.gate_count == 3  # 3 unique gates


def test_resolve_nonexistent():
    db = _get_test_db()
    dossier = resolve_entity(db, "nonexistent")
    assert dossier is None


def test_dossier_to_dict():
    db = _get_test_db()
    _seed_gate(db)
    dossier = resolve_entity(db, "gate-001")
    d = dossier.to_dict()
    assert isinstance(d, dict)
    assert d["entity_id"] == "gate-001"
    assert "danger_rating" in d
    assert "titles" in d
