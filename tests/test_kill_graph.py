"""Tests for kill graph analysis."""

import json
import sqlite3

import pytest

from backend.analysis.kill_graph import build_kill_graph
from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Create entities
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count, death_count)"
        " VALUES ('attacker-1', 'character', 'Hunter', 5, 0)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count, death_count)"
        " VALUES ('victim-1', 'character', 'Prey', 0, 3)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name, kill_count, death_count)"
        " VALUES ('attacker-2', 'character', 'Rival', 2, 2)"
    )

    # Killmails: attacker-1 killed victim-1 three times
    for i in range(3):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-{i}",
                "victim-1",
                json.dumps([{"address": "attacker-1"}]),
                "sys-A",
                1000 + i * 100,
            ),
        )

    # attacker-1 killed attacker-2 twice (vendetta setup)
    for i in range(2):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-v1-{i}",
                "attacker-2",
                json.dumps([{"address": "attacker-1"}]),
                "sys-B",
                2000 + i * 100,
            ),
        )

    # attacker-2 killed attacker-1 twice (vendetta: mutual kills)
    for i in range(2):
        conn.execute(
            "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
            " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                f"km-v2-{i}",
                "attacker-1",
                json.dumps([{"address": "attacker-2"}]),
                "sys-B",
                3000 + i * 100,
            ),
        )

    conn.commit()
    return conn


def test_global_kill_graph(db):
    result = build_kill_graph(db)
    assert result["total_edges"] > 0
    assert result["total_nodes"] > 0
    assert len(result["edges"]) > 0
    assert len(result["nodes"]) > 0


def test_entity_kill_graph(db):
    result = build_kill_graph(db, entity_id="attacker-1")
    assert result["total_edges"] > 0
    # attacker-1 should appear in edges
    attacker_ids = {e["attacker"] for e in result["edges"]}
    victim_ids = {e["victim"] for e in result["edges"]}
    assert "attacker-1" in attacker_ids or "attacker-1" in victim_ids


def test_vendetta_detection(db):
    result = build_kill_graph(db)
    assert len(result["vendettas"]) > 0
    vendetta = result["vendettas"][0]
    assert vendetta["total"] == 4  # 2 + 2
    pair = {vendetta["entity_1"], vendetta["entity_2"]}
    assert pair == {"attacker-1", "attacker-2"}


def test_min_kills_filter(db):
    result = build_kill_graph(db, min_kills=3)
    # Only attacker-1 → victim-1 (3 kills) should pass
    assert result["total_edges"] == 1
    assert result["edges"][0]["count"] == 3


def test_empty_graph(db):
    result = build_kill_graph(db, entity_id="nonexistent")
    assert result["total_edges"] == 0
    assert result["total_nodes"] == 0
    assert result["edges"] == []
    assert result["nodes"] == []


def test_edge_systems(db):
    result = build_kill_graph(db)
    # attacker-1 → victim-1 kills all in sys-A
    edge = next(e for e in result["edges"] if e["victim"] == "victim-1")
    assert "sys-A" in edge["systems"]


def test_node_display_names(db):
    result = build_kill_graph(db)
    names = {n["id"]: n["name"] for n in result["nodes"]}
    assert names.get("attacker-1") == "Hunter"
    assert names.get("victim-1") == "Prey"


def test_limit(db):
    result = build_kill_graph(db, limit=1)
    assert len(result["edges"]) == 1


def test_malformed_attacker_json(db):
    """Malformed JSON in attacker_character_ids should be skipped."""
    db.execute(
        "INSERT INTO killmails (killmail_id, victim_character_id, attacker_character_ids,"
        " solar_system_id, timestamp) VALUES (?, ?, ?, ?, ?)",
        ("km-bad", "victim-1", "not-json", "sys-A", 9000),
    )
    db.commit()
    # Should not crash
    result = build_kill_graph(db)
    assert result["total_edges"] > 0
