"""Tests for behavioral fingerprinting engine."""

import sqlite3

from backend.analysis.fingerprint import (
    RouteProfile,
    TemporalProfile,
    _cosine_similarity,
    _shannon_entropy,
    build_fingerprint,
    build_route_profile,
    build_social_profile,
    build_temporal_profile,
    build_threat_profile,
    compare_fingerprints,
    compute_opsec_score,
)
from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _seed_character(db, char_id="pilot-1", n_events=50):
    """Seed a character with gate events across multiple gates/hours."""
    db.execute(
        "INSERT INTO entities "
        "(entity_id, entity_type, display_name, "
        "event_count, kill_count, death_count, gate_count, "
        "first_seen, last_seen) "
        f"VALUES ('{char_id}', 'character', 'TestPilot', "
        f"{n_events}, 5, 2, {n_events}, 1000, {1000 + n_events * 3600})"
    )
    for i in range(n_events):
        gate = f"gate-{i % 5}"
        system = f"sys-{i % 3}"
        # Spread across different hours
        ts = 1000 + i * 3600
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('{gate}', '{char_id}', '{system}', {ts})"
        )
    db.commit()


# --- Shannon entropy ---


def test_entropy_uniform():
    """Uniform distribution has high entropy."""
    counts = {i: 10 for i in range(24)}
    e = _shannon_entropy(counts)
    assert e > 4.0


def test_entropy_concentrated():
    """Single-bucket distribution has zero entropy."""
    counts = {0: 100}
    e = _shannon_entropy(counts)
    assert e == 0.0


def test_entropy_empty():
    assert _shannon_entropy({}) == 0.0


# --- Temporal profile ---


def test_temporal_profile_basic():
    events = [{"timestamp": 3600 * h} for h in range(24)]
    profile = build_temporal_profile(events)
    assert profile.active_hours == 24
    assert profile.entropy > 4.0  # near-uniform


def test_temporal_profile_concentrated():
    # All events at same hour
    events = [{"timestamp": 3600 * 5 + i} for i in range(20)]
    profile = build_temporal_profile(events)
    assert profile.peak_hour == 5
    assert profile.peak_hour_pct == 100.0
    assert profile.entropy == 0.0


def test_temporal_profile_empty():
    profile = build_temporal_profile([])
    assert profile.active_hours == 0
    assert profile.entropy == 0.0


def test_temporal_profile_day_distribution():
    # Thursday (epoch day 0 is Thursday)
    events = [{"timestamp": i * 86400} for i in range(7)]
    profile = build_temporal_profile(events)
    assert len(profile.day_distribution) == 7


# --- Route profile ---


def test_route_profile_basic():
    events = [{"gate_id": f"g{i % 3}", "solar_system_id": f"s{i % 2}"} for i in range(30)]
    profile = build_route_profile(events)
    assert profile.unique_gates == 3
    assert profile.unique_systems == 2
    assert profile.top_gate in ("g0", "g1", "g2")


def test_route_profile_single_gate():
    events = [{"gate_id": "g1", "solar_system_id": "s1"} for _ in range(10)]
    profile = build_route_profile(events)
    assert profile.unique_gates == 1
    assert profile.top_gate_pct == 100.0
    assert profile.route_entropy == 0.0


def test_route_profile_empty():
    profile = build_route_profile([])
    assert profile.unique_gates == 0


# --- Social profile ---


def test_social_profile_with_associates():
    db = _get_test_db()
    # pilot-1 and pilot-2 transit same gate within window
    for i in range(10):
        ts = 1000 + i * 600
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'pilot-1', 's1', {ts})"
        )
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, corp_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'pilot-2', 'corp-x', 's1', {ts + 60})"
        )
    db.commit()

    events = [
        dict(r)
        for r in db.execute("SELECT * FROM gate_events WHERE character_id = 'pilot-1'").fetchall()
    ]

    profile = build_social_profile(db, "pilot-1", events)
    assert profile.unique_associates >= 1
    assert "pilot-2" in profile.co_transitors
    assert profile.solo_ratio == 0.0  # always has company


def test_social_profile_solo():
    db = _get_test_db()
    for i in range(5):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'loner', 's1', {1000 + i * 1000})"
        )
    db.commit()

    events = [
        dict(r)
        for r in db.execute("SELECT * FROM gate_events WHERE character_id = 'loner'").fetchall()
    ]

    profile = build_social_profile(db, "loner", events)
    assert profile.solo_ratio == 100.0
    assert profile.unique_associates == 0


# --- Threat profile ---


def test_threat_profile_killer():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities "
        "(entity_id, entity_type, "
        "kill_count, death_count, event_count, "
        "first_seen, last_seen) "
        "VALUES ('hunter', 'character', 25, 2, 50, 1000, 100000)"
    )
    db.commit()

    profile = build_threat_profile(db, "hunter")
    assert profile.kill_ratio > 0.9
    assert profile.threat_level == "extreme"


def test_threat_profile_pacifist():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities "
        "(entity_id, entity_type, "
        "kill_count, death_count, event_count, "
        "first_seen, last_seen) "
        "VALUES ('pacifist', 'character', 0, 0, 50, 1000, 100000)"
    )
    db.commit()

    profile = build_threat_profile(db, "pacifist")
    assert profile.threat_level == "none"
    assert profile.kill_ratio == 0.0


def test_threat_profile_nonexistent():
    db = _get_test_db()
    profile = build_threat_profile(db, "ghost")
    assert profile.threat_level == "unknown"


# --- OPSEC score ---


def test_opsec_high_entropy():
    """Diverse activity patterns = good OPSEC."""
    temporal = TemporalProfile(
        hour_distribution={i: 10 for i in range(24)},
        entropy=4.58,
    )
    route = RouteProfile(
        gate_frequency={f"g{i}": 5 for i in range(10)},
        unique_gates=10,
        route_entropy=3.32,
    )
    score, rating = compute_opsec_score(temporal, route)
    assert score >= 70
    assert rating in ("GOOD", "EXCELLENT")


def test_opsec_low_entropy():
    """Concentrated patterns = bad OPSEC."""
    temporal = TemporalProfile(
        hour_distribution={5: 100},
        entropy=0.0,
    )
    route = RouteProfile(
        gate_frequency={"g1": 100},
        unique_gates=1,
        route_entropy=0.0,
    )
    score, rating = compute_opsec_score(temporal, route)
    assert score <= 40
    assert rating in ("POOR", "FAIR")


# --- Full fingerprint ---


def test_build_fingerprint_character():
    db = _get_test_db()
    _seed_character(db)
    fp = build_fingerprint(db, "pilot-1")
    assert fp is not None
    assert fp.entity_type == "character"
    assert fp.event_count == 50
    assert fp.temporal.active_hours > 0
    assert fp.route.unique_gates == 5
    assert fp.opsec_score > 0


def test_build_fingerprint_gate():
    db = _get_test_db()
    db.execute(
        "INSERT INTO entities "
        "(entity_id, entity_type, display_name, "
        "event_count, kill_count, death_count, "
        "first_seen, last_seen) "
        "VALUES ('g1', 'gate', 'Alpha Gate', "
        "30, 0, 0, 1000, 50000)"
    )
    for i in range(30):
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('g1', 'c{i % 5}', 's1', {1000 + i * 3600})"
        )
    db.commit()

    fp = build_fingerprint(db, "g1")
    assert fp is not None
    assert fp.entity_type == "gate"
    assert fp.event_count == 30


def test_build_fingerprint_nonexistent():
    db = _get_test_db()
    assert build_fingerprint(db, "nope") is None


def test_fingerprint_to_dict():
    db = _get_test_db()
    _seed_character(db)
    fp = build_fingerprint(db, "pilot-1")
    d = fp.to_dict()
    assert isinstance(d, dict)
    assert "temporal" in d
    assert "route" in d
    assert "social" in d
    assert "threat" in d
    assert "opsec_score" in d
    assert "predictability" in d["temporal"]


# --- Fingerprint comparison ---


def test_compare_identical_fingerprints():
    db = _get_test_db()
    _seed_character(db, "pilot-1")
    fp1 = build_fingerprint(db, "pilot-1")
    result = compare_fingerprints(fp1, fp1)
    assert result["temporal_similarity"] == 1.0
    assert result["route_similarity"] == 1.0
    # Social is 0.0 for solo pilot (no co-transitors to compare)
    assert result["overall_similarity"] >= 0.6


def test_compare_different_fingerprints():
    db = _get_test_db()
    _seed_character(db, "pilot-1", 30)

    # Create a second pilot with different patterns
    db.execute(
        "INSERT INTO entities "
        "(entity_id, entity_type, display_name, "
        "event_count, kill_count, death_count, gate_count, "
        "first_seen, last_seen) "
        "VALUES ('pilot-2', 'character', 'Other', "
        "20, 0, 0, 20, 500000, 600000)"
    )
    for i in range(20):
        gate = f"gate-{i % 3 + 10}"  # different gates
        ts = 500000 + i * 7200  # different timing
        db.execute(
            "INSERT INTO gate_events "
            "(gate_id, character_id, "
            "solar_system_id, timestamp) "
            f"VALUES ('{gate}', 'pilot-2', 'sys-99', {ts})"
        )
    db.commit()

    fp1 = build_fingerprint(db, "pilot-1")
    fp2 = build_fingerprint(db, "pilot-2")
    result = compare_fingerprints(fp1, fp2)
    assert result["route_similarity"] == 0.0  # no gate overlap
    assert result["overall_similarity"] < 0.5
    assert result["likely_alt"] is False


# --- Cosine similarity ---


def test_cosine_identical():
    d = {0: 5, 1: 3, 2: 7}
    assert _cosine_similarity(d, d) == 1.0


def test_cosine_orthogonal():
    d1 = {0: 5}
    d2 = {1: 5}
    assert _cosine_similarity(d1, d2) == 0.0


def test_cosine_empty():
    assert _cosine_similarity({}, {}) == 0.0
