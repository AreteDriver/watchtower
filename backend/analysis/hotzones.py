"""Hotzone analysis — kill density by solar system.

Identifies dangerous systems by aggregating killmail data
across time windows. No coordinates needed — system-level only.
"""

import json
import sqlite3
import time
from dataclasses import dataclass

from backend.core.logger import get_logger

logger = get_logger("hotzones")

# Time windows in seconds
WINDOWS = {
    "24h": 86400,
    "7d": 7 * 86400,
    "30d": 30 * 86400,
    "all": 0,  # no time filter
}


@dataclass
class Hotzone:
    """A solar system with kill density stats."""

    solar_system_id: str
    solar_system_name: str
    kills: int = 0
    unique_attackers: int = 0
    unique_victims: int = 0
    latest_kill: int = 0

    def to_dict(self) -> dict:
        return {
            "solar_system_id": self.solar_system_id,
            "solar_system_name": self.solar_system_name,
            "kills": self.kills,
            "unique_attackers": self.unique_attackers,
            "unique_victims": self.unique_victims,
            "latest_kill": self.latest_kill,
            "danger_level": _danger_level(self.kills),
        }


def _danger_level(kills: int) -> str:
    """Classify danger level from kill count."""
    if kills >= 50:
        return "extreme"
    if kills >= 20:
        return "high"
    if kills >= 10:
        return "moderate"
    if kills >= 3:
        return "low"
    return "minimal"


def get_hotzones(
    db: sqlite3.Connection,
    window: str = "all",
    limit: int = 20,
) -> list[dict]:
    """Get top dangerous systems by kill count in a time window."""
    now = int(time.time())
    window_seconds = WINDOWS.get(window, 0)

    if window_seconds > 0:
        time_filter = "AND k.timestamp >= ?"
        params: list = [now - window_seconds, limit]
    else:
        time_filter = ""
        params = [limit]

    rows = db.execute(
        f"""SELECT k.solar_system_id,
                   COALESCE(sa.solar_system_name, '') as solar_system_name,
                   COUNT(*) as kills,
                   COUNT(DISTINCT k.victim_character_id) as unique_victims,
                   MAX(k.timestamp) as latest_kill
            FROM killmails k
            LEFT JOIN smart_assemblies sa
                ON k.solar_system_id = sa.solar_system_id
            WHERE k.solar_system_id != ''
                {time_filter}
            GROUP BY k.solar_system_id
            ORDER BY kills DESC
            LIMIT ?""",
        params,
    ).fetchall()

    hotzones = []
    for row in rows:
        hz = Hotzone(
            solar_system_id=row["solar_system_id"],
            solar_system_name=row["solar_system_name"] or "",
            kills=row["kills"],
            unique_victims=row["unique_victims"],
            latest_kill=row["latest_kill"],
        )

        # Count unique attackers separately (requires JSON parsing)
        attacker_rows = db.execute(
            """SELECT attacker_character_ids FROM killmails
               WHERE solar_system_id = ?"""
            + (f" AND timestamp >= {now - window_seconds}" if window_seconds > 0 else ""),
            (row["solar_system_id"],),
        ).fetchall()

        unique_attackers: set[str] = set()
        for ar in attacker_rows:
            try:
                attackers = json.loads(ar["attacker_character_ids"])
                for a in attackers:
                    addr = str(a.get("address") or a.get("characterId") or a.get("id", ""))
                    if addr:
                        unique_attackers.add(addr)
            except Exception:
                continue
        hz.unique_attackers = len(unique_attackers)

        hotzones.append(hz.to_dict())

    return hotzones


def get_system_activity(
    db: sqlite3.Connection,
    solar_system_id: str,
) -> dict:
    """Get detailed kill activity for a specific system."""
    kills = db.execute(
        """SELECT COUNT(*) as total,
                  MIN(timestamp) as first_kill,
                  MAX(timestamp) as last_kill
           FROM killmails WHERE solar_system_id = ?""",
        (solar_system_id,),
    ).fetchone()

    if not kills or kills["total"] == 0:
        return {"solar_system_id": solar_system_id, "total_kills": 0}

    # Kills by hour of day
    hour_rows = db.execute(
        """SELECT (timestamp % 86400) / 3600 as hour, COUNT(*) as cnt
           FROM killmails WHERE solar_system_id = ?
           GROUP BY hour ORDER BY hour""",
        (solar_system_id,),
    ).fetchall()
    hour_dist = {row["hour"]: row["cnt"] for row in hour_rows}

    # Top killers in this system
    top_killers = db.execute(
        """SELECT victim_character_id, COUNT(*) as deaths
           FROM killmails WHERE solar_system_id = ?
           AND victim_character_id != ''
           GROUP BY victim_character_id
           ORDER BY deaths DESC LIMIT 5""",
        (solar_system_id,),
    ).fetchall()

    return {
        "solar_system_id": solar_system_id,
        "total_kills": kills["total"],
        "first_kill": kills["first_kill"],
        "last_kill": kills["last_kill"],
        "hour_distribution": hour_dist,
        "top_victims": [dict(r) for r in top_killers],
        "danger_level": _danger_level(kills["total"]),
    }
