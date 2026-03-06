"""FastAPI routes — entity dossiers, story feed, watches, health."""

import json
import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.analysis.entity_resolver import resolve_entity
from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
from backend.analysis.narrative import generate_battle_report, generate_dossier_narrative
from backend.db.database import get_db

router = APIRouter()


@router.get("/health")
async def health():
    db = get_db()
    counts = {}
    for table in ("killmails", "gate_events", "entities", "story_feed", "watches"):
        row = db.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
        counts[table] = row["cnt"]
    return {"status": "ok", "tables": counts, "timestamp": int(time.time())}


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    db = get_db()
    dossier = resolve_entity(db, entity_id)
    if not dossier:
        raise HTTPException(status_code=404, detail="Entity not found")
    return dossier.to_dict()


@router.get("/entities")
async def list_entities(
    entity_type: str | None = None,
    sort: str = "event_count",
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    db = get_db()
    allowed_sorts = {"event_count", "last_seen", "kill_count", "death_count", "gate_count"}
    if sort not in allowed_sorts:
        sort = "event_count"

    where = "WHERE entity_type = ?" if entity_type else ""
    params = [entity_type] if entity_type else []

    rows = db.execute(
        f"""SELECT entity_id, entity_type, display_name, corp_id,
                   first_seen, last_seen, event_count, kill_count, death_count, gate_count
            FROM entities {where}
            ORDER BY {sort} DESC
            LIMIT ? OFFSET ?""",
        params + [limit, offset],
    ).fetchall()

    total = db.execute(f"SELECT COUNT(*) as cnt FROM entities {where}", params).fetchone()

    return {
        "entities": [dict(r) for r in rows],
        "total": total["cnt"],
        "limit": limit,
        "offset": offset,
    }


@router.get("/entity/{entity_id}/timeline")
async def get_entity_timeline(
    entity_id: str,
    start: int | None = None,
    end: int | None = None,
    limit: int = Query(default=100, le=500),
):
    """Unified timeline of all events for an entity."""
    db = get_db()
    now = int(time.time())
    start = start or (now - 7 * 86400)
    end = end or now

    events = []

    # Gate events
    gate_rows = db.execute(
        """SELECT 'gate_transit' as event_type, timestamp, gate_id, gate_name,
                  character_id, corp_id, solar_system_id, direction
           FROM gate_events
           WHERE timestamp BETWEEN ? AND ?
           AND (gate_id = ? OR character_id = ? OR corp_id = ?)
           ORDER BY timestamp ASC LIMIT ?""",
        (start, end, entity_id, entity_id, entity_id, limit),
    ).fetchall()
    events.extend([dict(r) for r in gate_rows])

    # Killmails
    kill_rows = db.execute(
        """SELECT 'killmail' as event_type, timestamp, killmail_id,
                  victim_character_id, victim_corp_id, solar_system_id, x, y, z
           FROM killmails
           WHERE timestamp BETWEEN ? AND ?
           AND (victim_character_id = ? OR victim_corp_id = ?
                OR attacker_character_ids LIKE ? OR attacker_corp_ids LIKE ?)
           ORDER BY timestamp ASC LIMIT ?""",
        (start, end, entity_id, entity_id, f'%"{entity_id}"%', f'%"{entity_id}"%', limit),
    ).fetchall()
    events.extend([dict(r) for r in kill_rows])

    events.sort(key=lambda e: e["timestamp"])

    # Add delta_seconds
    for i, event in enumerate(events):
        event["delta_seconds"] = 0 if i == 0 else event["timestamp"] - events[i - 1]["timestamp"]

    return {"entity_id": entity_id, "start": start, "end": end, "events": events}


@router.get("/feed")
async def get_story_feed(
    limit: int = Query(default=20, le=100),
    before: int | None = None,
):
    db = get_db()
    if before:
        rows = db.execute(
            """SELECT * FROM story_feed WHERE timestamp < ?
               ORDER BY timestamp DESC LIMIT ?""",
            (before, limit),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM story_feed ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    return {"items": [dict(r) for r in rows]}


@router.get("/leaderboard/{category}")
async def get_leaderboard(
    category: str,
    limit: int = Query(default=20, le=50),
):
    db = get_db()

    queries = {
        "deadliest_gates": """
            SELECT e.entity_id, e.display_name,
                   (SELECT COUNT(*) FROM killmails k WHERE k.solar_system_id =
                    (SELECT solar_system_id FROM gate_events WHERE gate_id = e.entity_id LIMIT 1)
                   ) as score
            FROM entities e WHERE e.entity_type = 'gate'
            ORDER BY score DESC LIMIT ?
        """,
        "most_active_gates": """
            SELECT entity_id, display_name, event_count as score
            FROM entities WHERE entity_type = 'gate'
            ORDER BY event_count DESC LIMIT ?
        """,
        "top_killers": """
            SELECT entity_id, display_name, kill_count as score
            FROM entities WHERE entity_type = 'character' AND kill_count > 0
            ORDER BY kill_count DESC LIMIT ?
        """,
        "most_deaths": """
            SELECT entity_id, display_name, death_count as score
            FROM entities WHERE entity_type = 'character' AND death_count > 0
            ORDER BY death_count DESC LIMIT ?
        """,
        "most_traveled": """
            SELECT entity_id, display_name, gate_count as score
            FROM entities WHERE entity_type = 'character'
            ORDER BY gate_count DESC LIMIT ?
        """,
    }

    if category not in queries:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category. Available: {list(queries.keys())}",
        )

    rows = db.execute(queries[category], (limit,)).fetchall()
    return {"category": category, "entries": [dict(r) for r in rows]}


@router.get("/titles")
async def get_titled_entities(limit: int = Query(default=50, le=200)):
    db = get_db()
    rows = db.execute(
        """SELECT t.entity_id, t.title, t.title_type, t.inscription_count,
                  e.entity_type, e.display_name
           FROM entity_titles t
           JOIN entities e ON t.entity_id = e.entity_id
           ORDER BY t.inscription_count DESC, t.computed_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return {"titles": [dict(r) for r in rows]}


@router.get("/search")
async def search_entities(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=20, le=50),
):
    db = get_db()
    pattern = f"%{q}%"
    rows = db.execute(
        """SELECT entity_id, entity_type, display_name, corp_id, event_count
           FROM entities
           WHERE entity_id LIKE ? OR display_name LIKE ? OR corp_id LIKE ?
           ORDER BY event_count DESC LIMIT ?""",
        (pattern, pattern, pattern, limit),
    ).fetchall()
    return {"query": q, "results": [dict(r) for r in rows]}


@router.get("/entity/{entity_id}/fingerprint")
async def get_entity_fingerprint(entity_id: str):
    db = get_db()
    fp = build_fingerprint(db, entity_id)
    if not fp:
        raise HTTPException(status_code=404, detail="Entity not found")
    return fp.to_dict()


@router.get("/fingerprint/compare")
async def compare_entity_fingerprints(
    entity_1: str = Query(...),
    entity_2: str = Query(...),
):
    db = get_db()
    fp1 = build_fingerprint(db, entity_1)
    fp2 = build_fingerprint(db, entity_2)
    if not fp1:
        raise HTTPException(404, f"Entity not found: {entity_1}")
    if not fp2:
        raise HTTPException(404, f"Entity not found: {entity_2}")
    return compare_fingerprints(fp1, fp2)


@router.get("/entity/{entity_id}/narrative")
async def get_entity_narrative(entity_id: str):
    narrative = generate_dossier_narrative(entity_id)
    return {"entity_id": entity_id, "narrative": narrative}


class BattleReportRequest(BaseModel):
    entity_id: str
    start: int
    end: int


@router.post("/battle-report")
async def create_battle_report(req: BattleReportRequest):
    db = get_db()
    events = []

    for table, id_cols in [
        ("gate_events", ["gate_id", "character_id", "corp_id"]),
        ("killmails", ["victim_character_id", "victim_corp_id", "solar_system_id"]),
    ]:
        for col in id_cols:
            rows = db.execute(
                f"""SELECT * FROM {table}
                    WHERE {col} = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC""",
                (req.entity_id, req.start, req.end),
            ).fetchall()
            events.extend([dict(r) for r in rows])

    # Deduplicate by (event_type implied by table, timestamp, entity)
    seen = set()
    unique_events = []
    for e in events:
        key = (e.get("killmail_id") or e.get("id"), e.get("timestamp"))
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    unique_events.sort(key=lambda e: e.get("timestamp", 0))

    if not unique_events:
        return {"error": "No events found for this query"}

    if len(unique_events) > 500:
        unique_events = unique_events[:500]

    report = generate_battle_report(unique_events)
    report["event_count"] = len(unique_events)
    return report


class WatchRequest(BaseModel):
    user_id: str
    watch_type: str
    target_id: str
    webhook_url: str = ""
    conditions: dict = {}


@router.post("/watches")
async def create_watch(req: WatchRequest):
    valid_types = {
        "entity_movement",
        "gate_traffic_spike",
        "killmail_proximity",
        "hostile_sighting",
    }
    if req.watch_type not in valid_types:
        raise HTTPException(400, f"Invalid type. Choose: {', '.join(valid_types)}")

    db = get_db()
    db.execute(
        """INSERT INTO watches (user_id, watch_type, target_id, conditions, webhook_url)
           VALUES (?, ?, ?, ?, ?)""",
        (req.user_id, req.watch_type, req.target_id, json.dumps(req.conditions), req.webhook_url),
    )
    db.commit()
    return {"status": "created", "watch_type": req.watch_type, "target_id": req.target_id}


@router.delete("/watches/{target_id}")
async def delete_watch(target_id: str, user_id: str):
    db = get_db()
    db.execute(
        "UPDATE watches SET active = 0 WHERE user_id = ? AND target_id = ? AND active = 1",
        (user_id, target_id),
    )
    db.commit()
    return {"status": "removed"}
