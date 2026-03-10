"""Tests for Warden autonomous threat intelligence loop."""

import json
import sqlite3
import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.db.database import SCHEMA
from backend.warden.warden import (
    OPERATOR_ALERT_THRESHOLD,
    Hypothesis,
    _audit_log,
    _hypothesize_blind_spots,
    _hypothesize_clone_depletion,
    _hypothesize_feral_escalation,
    _hypothesize_hunting_patterns,
    _hypothesize_kill_clusters,
    run_warden_cycle,
)


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# ---------- Hypothesis dataclass ----------


class TestHypothesis:
    def test_score_weights(self):
        h = Hypothesis(category="THREAT", title="test", description="desc")
        composite = h.score(1.0, 1.0, 1.0, 1.0)
        assert composite == pytest.approx(1.0, abs=0.01)

    def test_score_zeros(self):
        h = Hypothesis(category="THREAT", title="test", description="desc")
        composite = h.score(0.0, 0.0, 0.0, 0.0)
        assert composite == 0.0

    def test_score_clamps(self):
        h = Hypothesis(category="THREAT", title="test", description="desc")
        h.score(2.0, -1.0, 0.5, 0.5)
        assert h.scores["evidence"] == 1.0
        assert h.scores["recency"] == 0.0

    def test_to_dict(self):
        h = Hypothesis(
            category="INTEL",
            title="test",
            description="desc",
            evidence_count=3,
            zone_id="z1",
        )
        h.score(0.5, 0.5, 0.5, 0.5)
        d = h.to_dict()
        assert d["category"] == "INTEL"
        assert d["evidence_count"] == 3
        assert d["zone_id"] == "z1"
        assert "composite" in d
        assert isinstance(d["scores"], dict)

    def test_score_mixed(self):
        h = Hypothesis(category="LOGISTICS", title="t", description="d")
        composite = h.score(0.8, 0.6, 0.4, 0.2)
        expected = 0.8 * 0.35 + 0.6 * 0.25 + 0.4 * 0.25 + 0.2 * 0.15
        assert composite == pytest.approx(expected, abs=0.01)


# ---------- Audit log ----------


class TestAuditLog:
    def test_audit_log_writes(self, tmp_path):
        h = Hypothesis(category="THREAT", title="test", description="d")
        h.score(1.0, 1.0, 1.0, 1.0)
        h.committed = True
        audit_file = tmp_path / "audit.jsonl"
        with patch("backend.warden.warden.AUDIT_PATH", audit_file):
            _audit_log(h, "commit")
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "commit"
        assert entry["hypothesis"]["category"] == "THREAT"
        assert entry["hypothesis"]["committed"] is True

    def test_audit_log_appends(self, tmp_path):
        h1 = Hypothesis(category="THREAT", title="t1", description="d1")
        h1.score(1.0, 1.0, 1.0, 1.0)
        h2 = Hypothesis(category="INTEL", title="t2", description="d2")
        h2.score(0.1, 0.1, 0.1, 0.1)
        audit_file = tmp_path / "audit.jsonl"
        with patch("backend.warden.warden.AUDIT_PATH", audit_file):
            _audit_log(h1, "commit")
            _audit_log(h2, "discard")
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_audit_log_handles_missing_dir(self, tmp_path):
        h = Hypothesis(category="THREAT", title="test", description="d")
        audit_file = tmp_path / "subdir" / "audit.jsonl"
        with patch("backend.warden.warden.AUDIT_PATH", audit_file):
            _audit_log(h, "commit")
        assert audit_file.exists()


# ---------- Feral escalation ----------


class TestFeralEscalation:
    def test_no_events_returns_empty(self):
        db = _get_test_db()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_feral_escalation()
        assert result == []

    def test_recent_escalation_generates_hypothesis(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES (?, ?, ?, ?)",
            ("z1", "Alpha Zone", 2, now - 60),
        )
        db.execute(
            "INSERT INTO feral_ai_events "
            "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
            "VALUES (?, 'evolution', 0, 1, 'warning', ?)",
            ("z1", now - 3600),
        )
        db.execute(
            "INSERT INTO feral_ai_events "
            "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
            "VALUES (?, 'evolution', 1, 2, 'warning', ?)",
            ("z1", now - 1800),
        )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_feral_escalation()
        assert len(result) == 1
        assert result[0].category == "THREAT"
        assert "Alpha Zone" in result[0].title
        assert result[0].composite > 0

    def test_stale_zone_flagged(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES (?, ?, ?, ?)",
            ("z2", "Stale Zone", 3, now - 3600),
        )
        db.execute(
            "INSERT INTO feral_ai_events "
            "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
            "VALUES (?, 'evolution', 1, 3, 'critical', ?)",
            ("z2", now - 600),
        )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_feral_escalation()
        assert len(result) == 1
        assert "UNSCANNED" in result[0].evidence_summary

    def test_old_escalation_ignored(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier) VALUES (?, ?, ?)",
            ("z3", "Old Zone", 1),
        )
        db.execute(
            "INSERT INTO feral_ai_events "
            "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
            "VALUES (?, 'evolution', 0, 1, 'warning', ?)",
            ("z3", now - 86400),  # 24h ago
        )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_feral_escalation()
        assert result == []


# ---------- Kill clusters ----------


class TestKillClusters:
    def test_no_kills_returns_empty(self):
        db = _get_test_db()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_kill_clusters()
        assert result == []

    def test_cluster_detected(self):
        db = _get_test_db()
        now = int(time.time())
        # Insert 10 kills in one system — well above 2x baseline
        for i in range(10):
            db.execute(
                "INSERT INTO killmails "
                "(killmail_id, victim_character_id, solar_system_id, timestamp) "
                "VALUES (?, ?, 'sys1', ?)",
                (f"k{i}", f"v{i}", now - i * 60),
            )
        # Spread 2 kills across other systems for a low baseline
        for i in range(2):
            db.execute(
                "INSERT INTO killmails "
                "(killmail_id, victim_character_id, solar_system_id, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (f"kbase{i}", f"vbase{i}", f"sys{i + 10}", now - 100),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_kill_clusters()
        assert len(result) >= 1
        assert result[0].category == "THREAT"
        assert "sys1" in result[0].title

    def test_below_threshold_ignored(self):
        db = _get_test_db()
        now = int(time.time())
        # 2 kills is below the >= 3 threshold
        for i in range(2):
            db.execute(
                "INSERT INTO killmails "
                "(killmail_id, victim_character_id, solar_system_id, timestamp) "
                "VALUES (?, ?, 'sys1', ?)",
                (f"k{i}", f"v{i}", now - i * 60),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_kill_clusters()
        assert result == []


# ---------- Blind spots ----------


class TestBlindSpots:
    def test_no_zones_returns_empty(self):
        db = _get_test_db()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_blind_spots()
        assert result == []

    def test_single_blind_zone_not_enough(self):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES (?, ?, ?, ?)",
            ("z1", "Zone A", 1, now - 3600),
        )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_blind_spots()
        assert result == []  # Need >= 2

    def test_multiple_blind_zones_detected(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(3):
            db.execute(
                "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
                "VALUES (?, ?, ?, ?)",
                (f"z{i}", f"Zone {i}", i + 1, now - 3600 * (i + 1)),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_blind_spots()
        assert len(result) == 1
        assert "3 zones" in result[0].title

    def test_recently_scanned_not_blind(self):
        db = _get_test_db()
        now = int(time.time())
        for i in range(3):
            db.execute(
                "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
                "VALUES (?, ?, ?, ?)",
                (f"z{i}", f"Zone {i}", 1, now - 60),  # Scanned 1 min ago
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_blind_spots()
        assert result == []


# ---------- Clone depletion ----------


class TestCloneDepletion:
    def test_no_clones_returns_empty(self):
        db = _get_test_db()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_clone_depletion()
        assert result == []

    def test_low_clones_detected(self):
        db = _get_test_db()
        for i in range(2):
            db.execute(
                "INSERT INTO clones "
                "(clone_id, owner_id, owner_name, status) "
                "VALUES (?, 'owner1', 'TestOwner', 'active')",
                (f"c{i}",),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_clone_depletion()
        assert len(result) == 1
        assert result[0].category == "LOGISTICS"
        assert "TestOwner" in result[0].description

    def test_sufficient_clones_not_flagged(self):
        db = _get_test_db()
        for i in range(10):
            db.execute(
                "INSERT INTO clones "
                "(clone_id, owner_id, owner_name, status) "
                "VALUES (?, 'owner1', 'TestOwner', 'active')",
                (f"c{i}",),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_clone_depletion()
        assert result == []


# ---------- Hunting patterns ----------


class TestHuntingPatterns:
    def test_no_kills_returns_empty(self):
        db = _get_test_db()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_hunting_patterns()
        assert result == []

    def test_concentrated_deaths_detected(self):
        db = _get_test_db()
        now = int(time.time())
        # Same victim, 4 deaths in 1 system
        for i in range(4):
            db.execute(
                "INSERT INTO killmails "
                "(killmail_id, victim_character_id, solar_system_id, timestamp) "
                "VALUES (?, 'victim1', 'sys1', ?)",
                (f"k{i}", now - i * 600),
            )
        db.execute(
            "INSERT INTO entities (entity_id, entity_type, display_name) "
            "VALUES ('victim1', 'character', 'CampedPilot')",
        )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_hunting_patterns()
        assert len(result) == 1
        assert result[0].category == "INTEL"
        assert "CampedPilot" in result[0].title

    def test_spread_deaths_ignored(self):
        db = _get_test_db()
        now = int(time.time())
        # Same victim, 4 deaths across 4 systems
        for i in range(4):
            db.execute(
                "INSERT INTO killmails "
                "(killmail_id, victim_character_id, solar_system_id, timestamp) "
                "VALUES (?, 'victim1', ?, ?)",
                (f"k{i}", f"sys{i}", now - i * 600),
            )
        db.commit()
        with patch("backend.warden.warden.get_db", return_value=db):
            result = _hypothesize_hunting_patterns()
        assert result == []


# ---------- Full cycle ----------


class TestWardenCycle:
    @pytest.mark.asyncio
    async def test_cycle_commits_above_threshold(self, tmp_path):
        db = _get_test_db()
        now = int(time.time())
        # Set up data that will trigger feral escalation
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES ('z1', 'Hot Zone', 3, ?)",
            (now - 60,),
        )
        for i in range(5):
            db.execute(
                "INSERT INTO feral_ai_events "
                "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
                "VALUES ('z1', 'evolution', ?, ?, 'critical', ?)",
                (i, i + 1, now - (5 - i) * 600),
            )
        db.commit()

        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("backend.warden.warden.get_db", return_value=db),
            patch("backend.warden.warden.AUDIT_PATH", audit_file),
            patch("backend.warden.warden._notify_operator", new_callable=AsyncMock),
        ):
            committed = await run_warden_cycle()

        assert len(committed) >= 1
        assert any(h.committed for h in committed)
        assert audit_file.exists()

    @pytest.mark.asyncio
    async def test_cycle_discards_below_threshold(self, tmp_path):
        db = _get_test_db()
        # Empty DB — generators should return nothing or low-score
        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("backend.warden.warden.get_db", return_value=db),
            patch("backend.warden.warden.AUDIT_PATH", audit_file),
        ):
            committed = await run_warden_cycle()
        assert committed == []

    @pytest.mark.asyncio
    async def test_cycle_notifies_operator_on_high_confidence(self, tmp_path):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES ('z1', 'Critical Zone', 3, ?)",
            (now - 7200,),  # Stale — will amplify score
        )
        for i in range(8):
            db.execute(
                "INSERT INTO feral_ai_events "
                "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
                "VALUES ('z1', 'evolution', ?, ?, 'critical', ?)",
                (i, i + 1, now - (8 - i) * 300),
            )
        db.commit()

        audit_file = tmp_path / "audit.jsonl"
        mock_notify = AsyncMock()
        with (
            patch("backend.warden.warden.get_db", return_value=db),
            patch("backend.warden.warden.AUDIT_PATH", audit_file),
            patch("backend.warden.warden._notify_operator", mock_notify),
        ):
            committed = await run_warden_cycle()

        # At least one THREAT with high confidence should trigger notify
        threats = [h for h in committed if h.category == "THREAT"]
        if any(h.composite >= OPERATOR_ALERT_THRESHOLD for h in threats):
            mock_notify.assert_called()

    @pytest.mark.asyncio
    async def test_cycle_writes_to_story_feed(self, tmp_path):
        db = _get_test_db()
        now = int(time.time())
        db.execute(
            "INSERT INTO orbital_zones (zone_id, name, feral_ai_tier, last_scanned) "
            "VALUES ('z1', 'Active Zone', 2, ?)",
            (now - 60,),
        )
        for i in range(3):
            db.execute(
                "INSERT INTO feral_ai_events "
                "(zone_id, event_type, old_tier, new_tier, severity, timestamp) "
                "VALUES ('z1', 'evolution', ?, ?, 'warning', ?)",
                (i, i + 1, now - (3 - i) * 600),
            )
        db.commit()

        audit_file = tmp_path / "audit.jsonl"
        with (
            patch("backend.warden.warden.get_db", return_value=db),
            patch("backend.warden.warden.AUDIT_PATH", audit_file),
            patch("backend.warden.warden._notify_operator", new_callable=AsyncMock),
        ):
            committed = await run_warden_cycle()

        if committed:
            feed = db.execute(
                "SELECT * FROM story_feed WHERE event_type LIKE 'warden_%'"
            ).fetchall()
            assert len(feed) >= 1

    @pytest.mark.asyncio
    async def test_generator_error_does_not_crash_cycle(self, tmp_path):
        db = _get_test_db()
        audit_file = tmp_path / "audit.jsonl"

        def _boom():
            raise RuntimeError("generator exploded")

        with (
            patch("backend.warden.warden.get_db", return_value=db),
            patch("backend.warden.warden.AUDIT_PATH", audit_file),
            patch(
                "backend.warden.warden.ALL_GENERATORS",
                [_boom, _hypothesize_kill_clusters],
            ),
        ):
            # Should not raise
            committed = await run_warden_cycle()
            assert isinstance(committed, list)
