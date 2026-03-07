"""Naming engine — deterministic title generation from chain stats.

Every entity earns names based on their on-chain history.
Names are deterministic: same data = same name. Everyone sees the same titles.
"""

import sqlite3
from collections.abc import Callable

from backend.core.logger import get_logger

logger = get_logger("naming")


def _check(stats: dict, **conditions: int) -> bool:
    """Check stat conditions safely. Supports gte/eq/lte suffixed keys."""
    for key, threshold in conditions.items():
        if key.endswith("_gte"):
            if (stats.get(key[:-4]) or 0) < threshold:
                return False
        elif key.endswith("_eq"):
            if (stats.get(key[:-3]) or 0) != threshold:
                return False
        elif key.endswith("_lte"):
            if (stats.get(key[:-4]) or 0) > threshold:
                return False
        else:
            # Default: gte
            if (stats.get(key) or 0) < threshold:
                return False
    return True


# Title rules: (title, checker function)
GATE_TITLES: list[tuple[str, Callable[[dict], bool]]] = [
    ("The Meatgrinder", lambda s: _check(s, killmails_nearby_gte=20)),
    ("The Bloodgate", lambda s: _check(s, killmails_nearby_gte=10)),
    ("The Contested Passage", lambda s: _check(s, killmails_nearby_gte=5)),
    ("The Highway", lambda s: _check(s, event_count_gte=1000)),
    ("The Quiet Passage", lambda s: _check(s, event_count_gte=100, killmails_nearby_lte=2)),
    ("The Vault Gate", lambda s: _check(s, event_count_gte=50, killmails_nearby_eq=0)),
    ("The Crossroads", lambda s: _check(s, unique_pilots_gte=100)),
]

CHARACTER_TITLES: list[tuple[str, Callable[[dict], bool]]] = [
    ("The Pathfinder", lambda s: _check(s, gate_count_gte=50)),
    ("The Wanderer", lambda s: _check(s, gate_count_gte=20)),
    ("The Survivor", lambda s: _check(s, death_count_eq=0, event_count_gte=50)),
    ("The Marked", lambda s: _check(s, death_count_gte=10)),
    (
        "The Ghost",
        lambda s: _check(s, gate_count_gte=30, kill_count_eq=0, death_count_eq=0),
    ),
    ("The Hunter", lambda s: _check(s, kill_count_gte=20)),
    ("The Reaper", lambda s: _check(s, kill_count_gte=50)),
]

SYSTEM_TITLES: list[tuple[str, Callable[[dict], bool]]] = [
    ("The Graveyard", lambda s: _check(s, total_kills_gte=20)),
    ("The Warzone", lambda s: _check(s, total_kills_gte=10)),
    ("The Frontier", lambda s: _check(s, total_gates_gte=5, total_kills_gte=3)),
    ("The Safe Harbor", lambda s: _check(s, total_gates_gte=3, total_kills_eq=0)),
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

    stats = dict(row)
    return [title for title, check in GATE_TITLES if check(stats)]


def compute_character_titles(db: sqlite3.Connection, char_id: str) -> list[str]:
    """Compute earned titles for a character."""
    row = db.execute("SELECT * FROM entities WHERE entity_id = ?", (char_id,)).fetchone()
    if not row:
        return []

    stats = dict(row)
    return [title for title, check in CHARACTER_TITLES if check(stats)]


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
