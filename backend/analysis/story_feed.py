"""Story feed generator — auto-generates news items from on-chain events.

Runs periodically, detects notable events, creates feed items.
No AI required — rule-based detection with template rendering.
"""

import json
import time

from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("story_feed")


def _post_story(
    db,
    event_type: str,
    headline: str,
    body: str,
    entity_ids: list[str],
    severity: str = "info",
    timestamp: int | None = None,
):
    """Insert a story into the feed if not duplicate."""
    ts = timestamp or int(time.time())
    # Dedup: same headline within 1 hour
    existing = db.execute(
        """SELECT id FROM story_feed
           WHERE headline = ? AND timestamp > ?""",
        (headline, ts - 3600),
    ).fetchone()
    if existing:
        return

    db.execute(
        """INSERT INTO story_feed (event_type, headline, body, entity_ids, severity, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (event_type, headline, body, json.dumps(entity_ids), severity, ts),
    )


def detect_killmail_clusters(db, lookback_seconds: int = 3600) -> int:
    """Detect groups of killmails in the same system within a time window."""
    now = int(time.time())
    cutoff = now - lookback_seconds

    clusters = db.execute(
        """SELECT solar_system_id, COUNT(*) as cnt, MIN(timestamp) as first_ts,
                  MAX(timestamp) as last_ts
           FROM killmails
           WHERE timestamp > ? AND solar_system_id != ''
           GROUP BY solar_system_id
           HAVING cnt >= 3
           ORDER BY cnt DESC""",
        (cutoff,),
    ).fetchall()

    count = 0
    for cluster in clusters:
        duration = cluster["last_ts"] - cluster["first_ts"]
        duration_min = max(1, duration // 60)
        severity = (
            "critical" if cluster["cnt"] >= 8 else "warning" if cluster["cnt"] >= 5 else "info"
        )

        headline = (
            f"ENGAGEMENT: {cluster['cnt']} killmails in system "
            f"{cluster['solar_system_id'][:12]} in {duration_min} minutes"
        )
        body = f"{cluster['cnt']} ships destroyed over {duration_min} minutes."

        _post_story(
            db,
            "engagement",
            headline,
            body,
            [cluster["solar_system_id"]],
            severity,
            cluster["last_ts"],
        )
        count += 1
    return count


def detect_new_entities(db, lookback_seconds: int = 3600) -> int:
    """Detect entities appearing on-chain for the first time."""
    now = int(time.time())
    cutoff = now - lookback_seconds

    new_entities = db.execute(
        """SELECT entity_id, entity_type, display_name, corp_id
           FROM entities
           WHERE first_seen > ? AND event_count <= 3""",
        (cutoff,),
    ).fetchall()

    count = 0
    for entity in new_entities:
        if entity["entity_type"] == "character":
            corp_info = f" ({entity['corp_id'][:12]})" if entity["corp_id"] else ""
            name = entity["display_name"] or entity["entity_id"][:12]
            headline = f"NEW ENTITY: Character {name}{corp_info} — first appearance on-chain"
            _post_story(db, "new_entity", headline, "", [entity["entity_id"]], "info")
            count += 1
    return count


def detect_gate_milestones(db) -> int:
    """Detect gates hitting transit milestones."""
    milestones = [100, 500, 1000, 5000, 10000]
    count = 0

    for milestone in milestones:
        gates = db.execute(
            """SELECT entity_id, display_name, event_count FROM entities
               WHERE entity_type = 'gate' AND event_count >= ?
               AND event_count < ? + 50""",
            (milestone, milestone),
        ).fetchall()

        for gate in gates:
            name = gate["display_name"] or gate["entity_id"][:12]
            headline = f"MILESTONE: Gate {name} reached {milestone} transits"
            _post_story(db, "milestone", headline, "", [gate["entity_id"]], "info")
            count += 1
    return count


def detect_title_changes(db) -> int:
    """Post stories when entities earn new titles."""
    # Titles earned in the last hour
    now = int(time.time())
    cutoff = now - 3600

    new_titles = db.execute(
        """SELECT t.entity_id, t.title, e.entity_type, e.display_name
           FROM entity_titles t
           JOIN entities e ON t.entity_id = e.entity_id
           WHERE t.computed_at > ?""",
        (cutoff,),
    ).fetchall()

    count = 0
    for t in new_titles:
        name = t["display_name"] or t["entity_id"][:12]
        headline = (
            f'TITLE EARNED: {t["entity_type"].title()} {name} earned the title "{t["title"]}"'
        )
        _post_story(db, "title", headline, "", [t["entity_id"]], "info")
        count += 1
    return count


def generate_feed_items() -> int:
    """Run all detectors and generate new story feed items."""
    db = get_db()
    total = 0
    total += detect_killmail_clusters(db)
    total += detect_new_entities(db)
    total += detect_gate_milestones(db)
    total += detect_title_changes(db)

    if total > 0:
        db.commit()
        logger.info(f"Generated {total} new story feed items")
    return total
