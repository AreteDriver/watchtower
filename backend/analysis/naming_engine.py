"""Naming engine — deterministic title generation from chain stats.

Every entity earns names based on their on-chain history.
Names are deterministic: same data = same name. Everyone sees the same titles.
"""

import sqlite3

from backend.core.logger import get_logger

logger = get_logger("naming")

# Title rules: (title, entity_type, condition_sql, description)
GATE_TITLES = [
    ("The Meatgrinder", "killmails_nearby >= 20"),
    ("The Bloodgate", "killmails_nearby >= 10"),
    ("The Contested Passage", "killmails_nearby >= 5"),
    ("The Highway", "event_count >= 1000"),
    ("The Quiet Passage", "event_count >= 100 and killmails_nearby <= 2"),
    ("The Vault Gate", "event_count >= 50 and killmails_nearby == 0"),
    ("The Crossroads", "unique_pilots >= 100"),
]

CHARACTER_TITLES = [
    ("The Pathfinder", "gate_count >= 50"),
    ("The Wanderer", "gate_count >= 20"),
    ("The Survivor", "death_count == 0 and event_count >= 50"),
    ("The Marked", "death_count >= 10"),
    ("The Ghost", "gate_count >= 30 and kill_count == 0 and death_count == 0"),
    ("The Hunter", "kill_count >= 20"),
    ("The Reaper", "kill_count >= 50"),
]

SYSTEM_TITLES = [
    ("The Graveyard", "total_kills >= 20"),
    ("The Warzone", "total_kills >= 10"),
    ("The Frontier", "total_gates >= 5 and total_kills >= 3"),
    ("The Safe Harbor", "total_gates >= 3 and total_kills == 0"),
]


def compute_gate_titles(db: sqlite3.Connection, gate_id: str) -> list[str]:
    """Compute earned titles for a gate based on its stats."""
    row = db.execute(
        """SELECT
            e.event_count,
            e.kill_count,
            (SELECT COUNT(*) FROM killmails k
             WHERE k.solar_system_id = (
                 SELECT solar_system_id FROM gate_events WHERE gate_id = ? LIMIT 1
             )) as killmails_nearby,
            (SELECT COUNT(DISTINCT character_id)
            FROM gate_events WHERE gate_id = ?) as unique_pilots
        FROM entities e WHERE e.entity_id = ?""",
        (gate_id, gate_id, gate_id),
    ).fetchone()

    if not row:
        return []

    titles = []
    stats = dict(row)
    for title, condition in GATE_TITLES:
        try:
            if eval(condition, {"__builtins__": {}}, stats):
                titles.append(title)
        except Exception:
            continue
    return titles


def compute_character_titles(db: sqlite3.Connection, char_id: str) -> list[str]:
    """Compute earned titles for a character."""
    row = db.execute("SELECT * FROM entities WHERE entity_id = ?", (char_id,)).fetchone()
    if not row:
        return []

    titles = []
    stats = dict(row)
    for title, condition in CHARACTER_TITLES:
        try:
            if eval(condition, {"__builtins__": {}}, stats):
                titles.append(title)
        except Exception:
            continue
    return titles


def refresh_all_titles(db: sqlite3.Connection) -> int:
    """Recompute titles for all entities. Returns count of new titles."""
    count = 0

    # Gates
    gates = db.execute("SELECT entity_id FROM entities WHERE entity_type = 'gate'").fetchall()
    for gate in gates:
        titles = compute_gate_titles(db, gate["entity_id"])
        for title in titles:
            try:
                db.execute(
                    """INSERT INTO entity_titles (entity_id, title, title_type)
                       VALUES (?, ?, 'earned')
                       ON CONFLICT(entity_id, title) DO NOTHING""",
                    (gate["entity_id"], title),
                )
                count += 1
            except Exception:
                pass

    # Characters
    chars = db.execute("SELECT entity_id FROM entities WHERE entity_type = 'character'").fetchall()
    for char in chars:
        titles = compute_character_titles(db, char["entity_id"])
        for title in titles:
            try:
                db.execute(
                    """INSERT INTO entity_titles (entity_id, title, title_type)
                       VALUES (?, ?, 'earned')
                       ON CONFLICT(entity_id, title) DO NOTHING""",
                    (char["entity_id"], title),
                )
                count += 1
            except Exception:
                pass

    db.commit()
    return count
