"""Tests for narrative generation — template fallback and caching."""

import sqlite3
from unittest.mock import patch

import pytest

from backend.analysis.narrative import _template_narrative, generate_dossier_narrative
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
        "VALUES ('char-hunter', 'character', 'TestHunter',"
        " 100, 25, 3, 50, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('char-ghost', 'character', 'GhostPilot',"
        " 40, 0, 0, 30, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entities (entity_id, entity_type, display_name,"
        " event_count, kill_count, death_count, gate_count,"
        " first_seen, last_seen) "
        "VALUES ('gate-alpha', 'gate', 'Alpha Gate',"
        " 500, 15, 0, 0, 1000, 90000)"
    )
    conn.execute(
        "INSERT INTO entity_titles (entity_id, title, title_type) "
        "VALUES ('char-hunter', 'The Reaper', 'earned')"
    )
    conn.commit()
    return conn


def test_template_hunter_character():
    profile = {
        "entity_type": "character",
        "display_name": "TestHunter",
        "event_count": 100,
        "kill_count": 25,
        "death_count": 3,
        "gate_count": 50,
        "titles": ["The Reaper"],
        "danger_rating": "high",
    }
    text = _template_narrative(profile)
    assert "TestHunter" in text
    assert "The Reaper" in text
    assert "combat threat" in text
    assert "25" in text  # kills mentioned


def test_template_ghost_character():
    profile = {
        "entity_type": "character",
        "display_name": "GhostPilot",
        "event_count": 40,
        "kill_count": 0,
        "death_count": 0,
        "gate_count": 30,
        "titles": [],
        "danger_rating": "none",
    }
    text = _template_narrative(profile)
    assert "GhostPilot" in text
    assert "ghost" in text


def test_template_gate():
    profile = {
        "entity_type": "gate",
        "display_name": "Alpha Gate",
        "event_count": 500,
        "kill_count": 15,
        "titles": ["The Bloodgate"],
    }
    text = _template_narrative(profile)
    assert "Alpha Gate" in text
    assert "500 transits" in text
    assert "caution" in text


def test_template_gate_peaceful():
    profile = {
        "entity_type": "gate",
        "display_name": "Safe Gate",
        "event_count": 100,
        "kill_count": 0,
        "titles": [],
    }
    text = _template_narrative(profile)
    assert "Safe Gate" in text
    assert "peacefully" in text


def test_generate_uses_template_without_api_key(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text = generate_dossier_narrative("char-hunter")
        assert "TestHunter" in text
        assert len(text) > 50


def test_generate_caches_template_result(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text1 = generate_dossier_narrative("char-hunter")
        # Second call should return cached
        text2 = generate_dossier_narrative("char-hunter")
        assert text1 == text2
        # Verify it's in the cache table
        row = test_db.execute(
            "SELECT COUNT(*) as cnt FROM narrative_cache WHERE entity_id = 'char-hunter'"
        ).fetchone()
        assert row["cnt"] == 1


def test_generate_entity_not_found(test_db):
    with (
        patch("backend.analysis.narrative.get_db", return_value=test_db),
        patch("backend.analysis.narrative.settings") as mock_settings,
    ):
        mock_settings.ANTHROPIC_API_KEY = ""
        text = generate_dossier_narrative("nonexistent")
        assert text == "Entity not found."


def test_template_victim_character():
    profile = {
        "entity_type": "character",
        "display_name": "Victim",
        "event_count": 30,
        "kill_count": 1,
        "death_count": 8,
        "gate_count": 15,
        "titles": [],
        "danger_rating": "low",
    }
    text = _template_narrative(profile)
    assert "Victim" in text
    assert "losses" in text
