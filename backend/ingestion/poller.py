"""World API poller — the sensory system. NEVER LET THIS CRASH."""

import asyncio
import json
import time

import httpx

from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("poller")


async def poll_endpoint(client: httpx.AsyncClient, endpoint: str) -> list[dict]:
    """Single poll. Returns empty list on ANY failure."""
    url = f"{settings.WORLD_API_BASE}/{endpoint}"
    try:
        r = await client.get(url, timeout=settings.POLL_TIMEOUT_SECONDS)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "data" in data:
            return data["data"] if isinstance(data["data"], list) else [data["data"]]
        return [data] if data else []
    except httpx.TimeoutException:
        logger.warning(f"Timeout: {endpoint}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code}: {endpoint}")
    except Exception as e:
        logger.error(f"Poll error ({endpoint}): {e}")
    return []


def _ingest_killmails(db, killmails: list[dict]) -> int:
    """Ingest killmails. Returns count of new records."""
    count = 0
    for raw in killmails:
        # Field names are PLACEHOLDERS — confirm with explore_api.py
        killmail_id = raw.get("id") or raw.get("killmail_id") or raw.get("killMailId")
        if not killmail_id:
            continue

        try:
            db.execute(
                """INSERT OR IGNORE INTO killmails
                (killmail_id, victim_character_id, victim_corp_id,
                 attacker_character_ids, attacker_corp_ids,
                 solar_system_id, x, y, z, timestamp, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(killmail_id),
                    str(raw.get("victim", {}).get("characterId", "")),
                    str(raw.get("victim", {}).get("corporationId", "")),
                    json.dumps(raw.get("attackers", [])),
                    json.dumps(
                        list(
                            {
                                a.get("corporationId")
                                for a in raw.get("attackers", [])
                                if a.get("corporationId")
                            }
                        )
                    ),
                    str(raw.get("solarSystemId", "")),
                    raw.get("position", {}).get("x"),
                    raw.get("position", {}).get("y"),
                    raw.get("position", {}).get("z"),
                    int(raw.get("timestamp", time.time())),
                    json.dumps(raw),
                ),
            )
            count += 1
        except Exception as e:
            logger.error(f"Killmail ingest error: {e}")
    return count


def _ingest_gate_events(db, events: list[dict]) -> int:
    """Ingest gate transit events. Returns count of new records."""
    count = 0
    for raw in events:
        gate_id = raw.get("id") or raw.get("gateId") or raw.get("smartGateId")
        if not gate_id:
            continue

        try:
            db.execute(
                """INSERT INTO gate_events
                (gate_id, gate_name, character_id, corp_id,
                 solar_system_id, direction, timestamp, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(gate_id),
                    raw.get("name", ""),
                    str(raw.get("characterId", "")),
                    str(raw.get("corporationId", "")),
                    str(raw.get("solarSystemId", "")),
                    raw.get("direction", ""),
                    int(raw.get("timestamp", time.time())),
                    json.dumps(raw),
                ),
            )
            count += 1
        except Exception as e:
            logger.error(f"Gate event ingest error: {e}")
    return count


def _update_entities(db) -> None:
    """Rebuild entity stats from event tables. Lightweight — runs each cycle."""
    try:
        # Characters from killmails (victims)
        db.execute("""
            INSERT INTO entities (entity_id, entity_type,
                first_seen, last_seen, death_count, event_count)
            SELECT victim_character_id, 'character',
                   MIN(timestamp), MAX(timestamp), COUNT(*), COUNT(*)
            FROM killmails WHERE victim_character_id != ''
            GROUP BY victim_character_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = MAX(entities.last_seen, excluded.last_seen),
                death_count = excluded.death_count,
                event_count = entities.event_count + excluded.event_count,
                updated_at = unixepoch()
        """)

        # Characters from gate events
        db.execute("""
            INSERT INTO entities (entity_id, entity_type,
                first_seen, last_seen, gate_count, event_count)
            SELECT character_id, 'character',
                   MIN(timestamp), MAX(timestamp), COUNT(*), COUNT(*)
            FROM gate_events WHERE character_id != ''
            GROUP BY character_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = MAX(entities.last_seen, excluded.last_seen),
                gate_count = excluded.gate_count,
                event_count = entities.event_count + excluded.event_count,
                updated_at = unixepoch()
        """)

        # Gates as entities
        db.execute("""
            INSERT INTO entities (entity_id, entity_type, display_name,
                first_seen, last_seen, event_count)
            SELECT gate_id, 'gate', MAX(gate_name),
                   MIN(timestamp), MAX(timestamp), COUNT(*)
            FROM gate_events WHERE gate_id != ''
            GROUP BY gate_id
            ON CONFLICT(entity_id) DO UPDATE SET
                last_seen = MAX(entities.last_seen, excluded.last_seen),
                display_name = COALESCE(excluded.display_name, entities.display_name),
                event_count = excluded.event_count,
                updated_at = unixepoch()
        """)
    except Exception as e:
        logger.error(f"Entity update error: {e}")


async def run_poller() -> None:
    """Main ingestion loop. Runs forever. Never raises."""
    logger.info("Poller starting")
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Poll all endpoints in parallel
                kill_task = poll_endpoint(client, "killmails")
                gate_task = poll_endpoint(client, "smartgates")
                raw_kills, raw_gates = await asyncio.gather(kill_task, gate_task)

                db = get_db()
                new_kills = _ingest_killmails(db, raw_kills)
                new_gates = _ingest_gate_events(db, raw_gates)

                if new_kills or new_gates:
                    _update_entities(db)
                    db.commit()
                    logger.info(f"Ingested: {new_kills} killmails, {new_gates} gate events")
                else:
                    db.commit()

            except Exception as e:
                logger.critical(f"Poller loop error (continuing): {e}")

            await asyncio.sleep(settings.POLL_INTERVAL_SECONDS)
