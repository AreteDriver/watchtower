"""Behavioral fingerprinting — pattern analysis from on-chain activity.

Analyzes movement patterns, temporal habits, social connections,
and operational security from gate transits and killmails.
Every entity leaves a fingerprint. This module reads it.
"""

import math
import sqlite3
from dataclasses import dataclass, field

from backend.core.logger import get_logger

logger = get_logger("fingerprint")


@dataclass
class TemporalProfile:
    """When an entity is active."""

    hour_distribution: dict[int, int] = field(default_factory=dict)
    day_distribution: dict[int, int] = field(default_factory=dict)
    peak_hour: int = 0
    peak_day: int = 0
    peak_hour_pct: float = 0.0
    active_hours: int = 0  # hours with any activity
    entropy: float = 0.0  # Shannon entropy of hour distribution

    def to_dict(self) -> dict:
        day_names = [
            "Mon",
            "Tue",
            "Wed",
            "Thu",
            "Fri",
            "Sat",
            "Sun",
        ]
        return {
            "peak_hour": f"{self.peak_hour:02d}:00 UTC",
            "peak_day": day_names[self.peak_day] if self.peak_day < 7 else "?",
            "peak_hour_pct": round(self.peak_hour_pct, 1),
            "active_hours": self.active_hours,
            "entropy": round(self.entropy, 2),
            "predictability": _predictability_label(self.entropy),
        }


@dataclass
class RouteProfile:
    """Where an entity goes."""

    gate_frequency: dict[str, int] = field(default_factory=dict)
    system_frequency: dict[str, int] = field(default_factory=dict)
    top_gate: str = ""
    top_gate_pct: float = 0.0
    unique_gates: int = 0
    unique_systems: int = 0
    route_entropy: float = 0.0

    def to_dict(self) -> dict:
        return {
            "top_gate": self.top_gate[:20],
            "top_gate_pct": round(self.top_gate_pct, 1),
            "unique_gates": self.unique_gates,
            "unique_systems": self.unique_systems,
            "route_entropy": round(self.route_entropy, 2),
            "predictability": _predictability_label(self.route_entropy),
        }


@dataclass
class SocialProfile:
    """Who an entity associates with."""

    co_transitors: dict[str, int] = field(default_factory=dict)
    corp_associations: dict[str, int] = field(default_factory=dict)
    top_associate: str = ""
    top_associate_count: int = 0
    unique_associates: int = 0
    solo_ratio: float = 0.0  # % of transits with no co-transitor

    def to_dict(self) -> dict:
        top_5 = sorted(
            self.co_transitors.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        return {
            "top_associate": self.top_associate[:20],
            "top_associate_count": self.top_associate_count,
            "unique_associates": self.unique_associates,
            "solo_ratio": round(self.solo_ratio, 1),
            "top_5_associates": [{"id": cid[:20], "count": cnt} for cid, cnt in top_5],
        }


@dataclass
class ThreatProfile:
    """How dangerous an entity is."""

    kill_ratio: float = 0.0  # kills / (kills + deaths)
    kills_per_day: float = 0.0
    deaths_per_day: float = 0.0
    combat_zones: dict[str, int] = field(default_factory=dict)
    threat_level: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "kill_ratio": round(self.kill_ratio, 2),
            "kills_per_day": round(self.kills_per_day, 2),
            "deaths_per_day": round(self.deaths_per_day, 2),
            "threat_level": self.threat_level,
            "combat_zones": len(self.combat_zones),
        }


@dataclass
class Fingerprint:
    """Complete behavioral fingerprint for an entity."""

    entity_id: str
    entity_type: str
    event_count: int = 0
    temporal: TemporalProfile = field(default_factory=TemporalProfile)
    route: RouteProfile = field(default_factory=RouteProfile)
    social: SocialProfile = field(default_factory=SocialProfile)
    threat: ThreatProfile = field(default_factory=ThreatProfile)
    opsec_score: int = 0
    opsec_rating: str = "UNKNOWN"

    def to_dict(self) -> dict:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "event_count": self.event_count,
            "temporal": self.temporal.to_dict(),
            "route": self.route.to_dict(),
            "social": self.social.to_dict(),
            "threat": self.threat.to_dict(),
            "opsec_score": self.opsec_score,
            "opsec_rating": self.opsec_rating,
        }


# --- Core analysis functions ---


def _shannon_entropy(counts: dict) -> float:
    """Shannon entropy of a frequency distribution. Higher = less predictable."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _predictability_label(entropy: float) -> str:
    """Human-readable predictability from entropy value."""
    if entropy < 2.0:
        return "highly predictable"
    if entropy < 3.0:
        return "somewhat predictable"
    if entropy < 4.0:
        return "moderate"
    return "unpredictable"


def build_temporal_profile(events: list[dict]) -> TemporalProfile:
    """Analyze when an entity is active from timestamped events."""
    profile = TemporalProfile()
    if not events:
        return profile

    for e in events:
        ts = e.get("timestamp", 0)
        hour = (ts % 86400) // 3600
        # weekday from epoch (Jan 1 1970 was Thursday = 3)
        day = ((ts // 86400) + 3) % 7
        profile.hour_distribution[hour] = profile.hour_distribution.get(hour, 0) + 1
        profile.day_distribution[day] = profile.day_distribution.get(day, 0) + 1

    total = sum(profile.hour_distribution.values())
    if total > 0:
        profile.peak_hour = max(
            profile.hour_distribution,
            key=profile.hour_distribution.get,
        )
        profile.peak_hour_pct = profile.hour_distribution[profile.peak_hour] / total * 100
    if profile.day_distribution:
        profile.peak_day = max(
            profile.day_distribution,
            key=profile.day_distribution.get,
        )
    profile.active_hours = len(profile.hour_distribution)
    profile.entropy = _shannon_entropy(profile.hour_distribution)

    return profile


def build_route_profile(events: list[dict]) -> RouteProfile:
    """Analyze where an entity goes from gate transit events."""
    profile = RouteProfile()
    if not events:
        return profile

    for e in events:
        gate = e.get("gate_id", "")
        system = e.get("solar_system_id", "")
        if gate:
            profile.gate_frequency[gate] = profile.gate_frequency.get(gate, 0) + 1
        if system:
            profile.system_frequency[system] = profile.system_frequency.get(system, 0) + 1

    profile.unique_gates = len(profile.gate_frequency)
    profile.unique_systems = len(profile.system_frequency)

    total = sum(profile.gate_frequency.values())
    if total > 0 and profile.gate_frequency:
        profile.top_gate = max(
            profile.gate_frequency,
            key=profile.gate_frequency.get,
        )
        profile.top_gate_pct = profile.gate_frequency[profile.top_gate] / total * 100
    profile.route_entropy = _shannon_entropy(profile.gate_frequency)

    return profile


CO_TRANSIT_WINDOW = 300  # 5 minutes


def build_social_profile(
    db: sqlite3.Connection,
    entity_id: str,
    events: list[dict],
) -> SocialProfile:
    """Analyze who an entity associates with via co-transit detection."""
    profile = SocialProfile()
    if not events:
        return profile

    solo_count = 0

    for e in events:
        gate_id = e.get("gate_id", "")
        ts = e.get("timestamp", 0)
        if not gate_id or not ts:
            continue

        # Find others at same gate within time window
        nearby = db.execute(
            """SELECT DISTINCT character_id FROM gate_events
               WHERE gate_id = ? AND character_id != ?
               AND timestamp BETWEEN ? AND ?""",
            (gate_id, entity_id, ts - CO_TRANSIT_WINDOW, ts + CO_TRANSIT_WINDOW),
        ).fetchall()

        if not nearby:
            solo_count += 1
        for row in nearby:
            cid = row["character_id"]
            profile.co_transitors[cid] = profile.co_transitors.get(cid, 0) + 1

        # Track corp associations
        corp_rows = db.execute(
            """SELECT DISTINCT corp_id FROM gate_events
               WHERE gate_id = ? AND character_id != ?
               AND corp_id != '' AND timestamp BETWEEN ? AND ?""",
            (gate_id, entity_id, ts - CO_TRANSIT_WINDOW, ts + CO_TRANSIT_WINDOW),
        ).fetchall()
        for row in corp_rows:
            corp = row["corp_id"]
            profile.corp_associations[corp] = profile.corp_associations.get(corp, 0) + 1

    profile.unique_associates = len(profile.co_transitors)
    total = len(events)
    profile.solo_ratio = solo_count / total * 100 if total else 0.0

    if profile.co_transitors:
        profile.top_associate = max(
            profile.co_transitors,
            key=profile.co_transitors.get,
        )
        profile.top_associate_count = profile.co_transitors[profile.top_associate]

    return profile


def build_threat_profile(
    db: sqlite3.Connection,
    entity_id: str,
) -> ThreatProfile:
    """Analyze combat behavior from killmail data."""
    profile = ThreatProfile()

    entity = db.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not entity:
        return profile

    kills = entity["kill_count"] or 0
    deaths = entity["death_count"] or 0
    total_combat = kills + deaths

    if total_combat > 0:
        profile.kill_ratio = kills / total_combat

    first = entity["first_seen"] or 0
    last = entity["last_seen"] or 0
    days_active = max(1, (last - first) / 86400)
    profile.kills_per_day = kills / days_active
    profile.deaths_per_day = deaths / days_active

    # Combat zones from killmails
    kill_systems = db.execute(
        """SELECT solar_system_id, COUNT(*) as cnt FROM killmails
           WHERE victim_character_id = ?
              OR attacker_character_ids LIKE ?
           GROUP BY solar_system_id""",
        (entity_id, f'%"{entity_id}"%'),
    ).fetchall()
    for row in kill_systems:
        profile.combat_zones[row["solar_system_id"]] = row["cnt"]

    # Threat level classification
    if kills >= 50 or profile.kills_per_day >= 2.0:
        profile.threat_level = "extreme"
    elif kills >= 20 or profile.kills_per_day >= 1.0:
        profile.threat_level = "high"
    elif kills >= 5 or profile.kills_per_day >= 0.3:
        profile.threat_level = "moderate"
    elif kills > 0:
        profile.threat_level = "low"
    else:
        profile.threat_level = "none"

    return profile


def compute_opsec_score(
    temporal: TemporalProfile,
    route: RouteProfile,
) -> tuple[int, str]:
    """Compute OPSEC score from temporal and route profiles.

    0-100 where 100 is best operational security.
    """
    # Time predictability (high entropy = good OPSEC)
    # Max possible entropy for 24 hours = log2(24) ≈ 4.58
    time_score = min(100, temporal.entropy / 4.58 * 100)

    # Route predictability (high entropy = good OPSEC)
    # Normalize against unique gates used
    max_route_entropy = math.log2(max(1, route.unique_gates))
    route_score = (
        min(100, route.route_entropy / max_route_entropy * 100) if max_route_entropy > 0 else 0
    )

    # Gate diversity bonus
    diversity_score = min(100, route.unique_gates * 10)

    score = int((time_score + route_score + diversity_score) / 3)
    score = max(0, min(100, score))

    if score >= 80:
        rating = "EXCELLENT"
    elif score >= 60:
        rating = "GOOD"
    elif score >= 40:
        rating = "FAIR"
    else:
        rating = "POOR"

    return score, rating


def build_fingerprint(
    db: sqlite3.Connection,
    entity_id: str,
) -> Fingerprint | None:
    """Build complete behavioral fingerprint for an entity."""
    entity = db.execute(
        "SELECT * FROM entities WHERE entity_id = ?",
        (entity_id,),
    ).fetchone()
    if not entity:
        return None

    entity_type = entity["entity_type"]

    # Gather gate events for this entity
    if entity_type == "character":
        events = db.execute(
            """SELECT gate_id, solar_system_id, timestamp
               FROM gate_events WHERE character_id = ?
               ORDER BY timestamp ASC""",
            (entity_id,),
        ).fetchall()
    elif entity_type == "gate":
        events = db.execute(
            """SELECT gate_id, character_id, solar_system_id, timestamp
               FROM gate_events WHERE gate_id = ?
               ORDER BY timestamp ASC""",
            (entity_id,),
        ).fetchall()
    else:
        events = []

    event_dicts = [dict(e) for e in events]

    fp = Fingerprint(
        entity_id=entity_id,
        entity_type=entity_type,
        event_count=len(event_dicts),
    )

    fp.temporal = build_temporal_profile(event_dicts)
    fp.route = build_route_profile(event_dicts)

    if entity_type == "character":
        fp.social = build_social_profile(db, entity_id, event_dicts)

    fp.threat = build_threat_profile(db, entity_id)
    fp.opsec_score, fp.opsec_rating = compute_opsec_score(
        fp.temporal,
        fp.route,
    )

    return fp


def compare_fingerprints(
    fp1: Fingerprint,
    fp2: Fingerprint,
) -> dict:
    """Compare two fingerprints for similarity.

    Returns similarity scores across dimensions.
    Useful for: alt detection, fleet coordination analysis,
    pattern matching between entities.
    """
    # Temporal similarity (cosine similarity of hour distributions)
    temporal_sim = _cosine_similarity(
        fp1.temporal.hour_distribution,
        fp2.temporal.hour_distribution,
    )

    # Route similarity (Jaccard index of gates used)
    gates1 = set(fp1.route.gate_frequency.keys())
    gates2 = set(fp2.route.gate_frequency.keys())
    route_sim = len(gates1 & gates2) / len(gates1 | gates2) if (gates1 | gates2) else 0.0

    # Social similarity (overlap in associates)
    assoc1 = set(fp1.social.co_transitors.keys())
    assoc2 = set(fp2.social.co_transitors.keys())
    social_sim = len(assoc1 & assoc2) / len(assoc1 | assoc2) if (assoc1 | assoc2) else 0.0

    overall = (temporal_sim + route_sim + social_sim) / 3

    return {
        "entity_1": fp1.entity_id,
        "entity_2": fp2.entity_id,
        "temporal_similarity": round(temporal_sim, 3),
        "route_similarity": round(route_sim, 3),
        "social_similarity": round(social_sim, 3),
        "overall_similarity": round(overall, 3),
        "likely_alt": overall > 0.7,
        "likely_fleet_mate": route_sim > 0.5 and temporal_sim > 0.5,
    }


def _cosine_similarity(d1: dict, d2: dict) -> float:
    """Cosine similarity between two frequency dicts."""
    keys = set(d1.keys()) | set(d2.keys())
    if not keys:
        return 0.0
    dot = sum(d1.get(k, 0) * d2.get(k, 0) for k in keys)
    mag1 = math.sqrt(sum(v * v for v in d1.values()))
    mag2 = math.sqrt(sum(v * v for v in d2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)
