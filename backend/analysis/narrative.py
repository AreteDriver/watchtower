"""AI narrative engine — generates dossier bios and battle reports.

Uses Anthropic API. All generated content is cached by entity + event hash
to avoid redundant API calls.
"""

import hashlib
import json

import anthropic

from backend.analysis.entity_resolver import resolve_entity
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("narrative")


def _track_usage(msg, operation: str, entity_id: str = "") -> None:
    """Record Anthropic API token usage to ai_usage table."""
    try:
        usage = msg.usage
        db = get_db()
        db.execute(
            """INSERT INTO ai_usage (model, operation, input_tokens, output_tokens,
               cached_tokens, entity_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                msg.model,
                operation,
                usage.input_tokens,
                usage.output_tokens,
                getattr(usage, "cache_read_input_tokens", 0) or 0,
                entity_id,
            ),
        )
        db.commit()
    except Exception as e:
        logger.debug("Usage tracking error (non-fatal): %s", e)


DOSSIER_SYSTEM = """You are the WatchTower — the living memory of EVE Frontier.
You analyze on-chain event data and write concise, evocative dossier entries
for game entities (gates, characters, corps, solar systems).

Write in the style of an intelligence briefing crossed with a history book.
Be specific — cite event counts, timestamps, patterns. Never invent data
not present in the input. Flag uncertainty when data is sparse.

Keep responses under 300 words. No markdown headers. Just prose."""

DOSSIER_USER = """Write a dossier entry for this EVE Frontier entity.

ENTITY PROFILE:
{profile_json}

RECENT TIMELINE (last 50 events):
{timeline_json}

Write a 2-3 paragraph dossier covering:
1. Who/what this entity is and their significance
2. Notable patterns, events, or behaviors
3. Current status and what to watch for"""

SYSTEM_DOSSIER_USER = """Write a system intelligence briefing for this solar system in EVE Frontier.

SYSTEM: {system_name} ({system_id})

COMBAT DATA:
- Total kills: {kill_count}
- Kills (24h): {kills_24h}
- Kills (7d): {kills_7d}
- Unique attackers: {unique_attackers}
- Unique victims: {unique_victims}
- Gate transits: {gate_transits}
- Danger level: {danger_level}

TOP ATTACKERS:
{top_attackers_json}

INFRASTRUCTURE:
- Smart assemblies in system: {assembly_count}

Write a 2-3 paragraph system intelligence briefing covering:
1. The system's strategic significance and threat profile
2. Notable patterns — who operates here, when activity peaks, how dangerous transit is
3. Recommendations for pilots entering this system"""

BATTLE_SYSTEM = """You are a tactical analyst for EVE Frontier.
You reconstruct engagements from on-chain event sequences.
Think like an NTSB investigator — methodical, evidence-based,
focused on the sequence of decisions that led to the outcome.

Always structure response as valid JSON matching the schema provided.
Never invent events not present in the data."""

BATTLE_USER = """Analyze this EVE Frontier engagement and produce a structured report.

TIMELINE ({event_count} events, {duration_seconds}s duration):
{timeline_json}

Produce JSON:
{{
  "title": "Short battle name (e.g. 'The Battle of X-7')",
  "summary": "2-3 sentence summary",
  "narrative": [
    {{"timestamp": <int>, "description": "What happened",
      "significance": "low|medium|high|critical"}}
  ],
  "key_moments": [
    {{"timestamp": <int>, "description": "Turning point or key decision"}}
  ],
  "anomalies": [
    {{"type": "timing|unknown_actor|pattern_break", "description": "What was unusual"}}
  ],
  "outcome": "Who won, what was lost, what changed",
  "lessons": ["Actionable recommendation"]
}}"""


def _get_client() -> anthropic.Anthropic:
    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _event_hash(data: dict | list) -> str:
    raw = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_cached(db, entity_id: str, narrative_type: str, event_hash: str) -> str | None:
    row = db.execute(
        """SELECT content FROM narrative_cache
           WHERE entity_id = ? AND narrative_type = ? AND event_hash = ?""",
        (entity_id, narrative_type, event_hash),
    ).fetchone()
    return row["content"] if row else None


def _store_cache(db, entity_id: str, narrative_type: str, event_hash: str, content: str):
    db.execute(
        """INSERT OR REPLACE INTO narrative_cache
           (entity_id, narrative_type, event_hash, content)
           VALUES (?, ?, ?, ?)""",
        (entity_id, narrative_type, event_hash, content),
    )
    db.commit()


def _template_narrative(profile: dict) -> str:
    """Generate a template-based narrative when no AI API key is available."""
    d = profile
    name = d.get("display_name") or d.get("entity_id", "Unknown")[:16]
    etype = d.get("entity_type", "entity")
    events = d.get("event_count", 0)
    kills = d.get("kill_count", 0)
    deaths = d.get("death_count", 0)
    gates = d.get("gate_count", 0)
    titles = d.get("titles", [])
    danger = d.get("danger_rating", "unknown")

    parts = []

    if etype == "character":
        title_str = f', known as "{titles[0]}"' if titles else ""
        parts.append(
            f"{name}{title_str} has been observed across the frontier with "
            f"{events} recorded events. Their on-chain footprint spans "
            f"{gates} gate transits, {kills} confirmed kills, and {deaths} losses."
        )
        if kills > deaths and kills > 5:
            parts.append(
                f"Analysis marks this pilot as a significant combat threat "
                f"(danger rating: {danger}). Their kill-to-death ratio suggests "
                f"a seasoned hunter who chooses engagements carefully."
            )
        elif deaths > kills and deaths > 3:
            parts.append(
                "This pilot has suffered more losses than victories, suggesting "
                "either a trader navigating dangerous space or a pilot still "
                "learning the harsh realities of the frontier."
            )
        elif kills == 0 and deaths == 0 and gates > 20:
            parts.append(
                f"No combat record exists for this entity. With {gates} gate "
                f"transits and zero engagements, this appears to be a ghost — "
                f"moving through the frontier without leaving a mark."
            )
        else:
            parts.append(
                "Their activity pattern suggests a balanced operator, neither "
                "pure combatant nor pure trader."
            )
    elif etype == "gate":
        parts.append(f"Gate {name} has channeled {events} transits through its structure. ")
        if kills > 5:
            parts.append(
                f"With {kills} recorded kills in the vicinity, this gate has earned "
                f"its reputation as contested space. Pilots transiting here should "
                f"exercise caution."
            )
        else:
            parts.append(
                "Traffic flows relatively peacefully through this passage, though "
                "the frontier is never truly safe."
            )
    else:
        parts.append(f"{name} — {events} events recorded on-chain.")

    if titles:
        parts.append(f"Earned titles: {', '.join(titles)}.")

    return "\n\n".join(parts)


def generate_dossier_narrative(entity_id: str) -> str:
    """Generate a dossier entry for an entity. Uses AI when available, templates otherwise."""
    db = get_db()
    dossier = resolve_entity(db, entity_id)
    if not dossier:
        return "Entity not found."

    # Build timeline for context
    events = []
    for table, id_col in [
        ("gate_events", "gate_id"),
        ("gate_events", "character_id"),
        ("killmails", "victim_character_id"),
    ]:
        rows = db.execute(
            f"""SELECT * FROM {table} WHERE {id_col} = ?
                ORDER BY timestamp DESC LIMIT 25""",
            (entity_id,),
        ).fetchall()
        events.extend([dict(r) for r in rows])

    events.sort(key=lambda e: e.get("timestamp", 0))
    events = events[-50:]  # Last 50

    profile_data = dossier.to_dict()

    # Check cache
    eh = _event_hash({"profile": profile_data, "events": events})
    cached = _get_cached(db, entity_id, "dossier", eh)
    if cached:
        return cached

    # Fallback to template narrative if no API key
    if not settings.ANTHROPIC_API_KEY:
        content = _template_narrative(profile_data)
        _store_cache(db, entity_id, "dossier", eh, content)
        return content

    # Generate with AI
    try:
        client = _get_client()
        # Strip raw_json from events to save tokens
        clean_events = [{k: v for k, v in e.items() if k != "raw_json"} for e in events]

        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=DOSSIER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": DOSSIER_USER.format(
                        profile_json=json.dumps(profile_data, indent=2),
                        timeline_json=json.dumps(clean_events, indent=2, default=str),
                    ),
                }
            ],
        )
        content = msg.content[0].text
        _track_usage(msg, "dossier", entity_id)
        _store_cache(db, entity_id, "dossier", eh, content)
        logger.info("Generated dossier for %s", entity_id)
        return content
    except ValueError:
        logger.exception("Narrative generation error")
        return "Narrative temporarily unavailable."
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        return _template_narrative(profile_data)


def _template_system_narrative(system_name: str, stats: dict) -> str:
    """Generate a template-based system narrative when no AI API key is available."""
    kill_count = stats.get("total_kills", 0)
    danger = stats.get("danger_level", "unknown")
    attackers = stats.get("unique_attackers", 0)
    victims = stats.get("unique_victims", 0)
    gate_transits = stats.get("gate_transits", 0)
    assembly_count = stats.get("assembly_count", 0)
    top_attackers = stats.get("top_attackers", [])

    parts = []

    if kill_count == 0:
        parts.append(
            f"{system_name} shows no recorded kill activity. This system appears "
            f"to be either uninhabited or a peaceful transit corridor."
        )
        if gate_transits > 0:
            parts.append(
                f"With {gate_transits} gate transits recorded, pilots pass through "
                f"without incident — for now."
            )
    else:
        parts.append(
            f"{system_name} carries a {danger} threat rating with {kill_count} "
            f"confirmed kills on record. {attackers} unique attackers have operated "
            f"here, claiming {victims} distinct victims."
        )
        if top_attackers:
            names = [a.get("display_name", "Unknown") for a in top_attackers[:3]]
            parts.append(
                f"The most lethal operators in this system include: {', '.join(names)}. "
                f"Pilots transiting should exercise caution and check recent activity."
            )

    if assembly_count > 0:
        parts.append(
            f"Infrastructure scan reveals {assembly_count} smart "
            f"assembl{'y' if assembly_count == 1 else 'ies'} "
            f"deployed in system, indicating active territorial investment."
        )

    return "\n\n".join(parts)


def generate_system_narrative(system_id: str) -> str:
    """Generate a system intelligence briefing. Uses AI when available, templates otherwise."""
    db = get_db()

    # Get system name
    sys_row = db.execute(
        "SELECT name FROM solar_systems WHERE solar_system_id = ?", (system_id,)
    ).fetchone()
    system_name = sys_row["name"] if sys_row else system_id[:16]

    # Gather system stats
    kill_row = db.execute(
        """SELECT COUNT(*) as total_kills,
                  COUNT(DISTINCT victim_character_id) as unique_victims,
                  SUM(CASE WHEN timestamp > ? THEN 1 ELSE 0 END) as kills_24h,
                  SUM(CASE WHEN timestamp > ? THEN 1 ELSE 0 END) as kills_7d
           FROM killmails WHERE solar_system_id = ?""",
        (
            int(__import__("time").time()) - 86400,
            int(__import__("time").time()) - 7 * 86400,
            system_id,
        ),
    ).fetchone()

    unique_attackers_row = db.execute(
        """SELECT COUNT(DISTINCT attacker_character_ids) as cnt
           FROM killmails WHERE solar_system_id = ?""",
        (system_id,),
    ).fetchone()

    gate_row = db.execute(
        "SELECT COUNT(*) as cnt FROM gate_events WHERE solar_system_id = ?",
        (system_id,),
    ).fetchone()

    assembly_row = db.execute(
        "SELECT COUNT(*) as cnt FROM smart_assemblies WHERE solar_system_id = ?",
        (system_id,),
    ).fetchone()

    top_attackers = db.execute(
        """SELECT e.entity_id, e.display_name, COUNT(*) as kills
           FROM killmails k
           JOIN entities e ON e.entity_id IN (
               SELECT value FROM json_each(k.attacker_character_ids)
           )
           WHERE k.solar_system_id = ?
           GROUP BY e.entity_id
           ORDER BY kills DESC LIMIT 5""",
        (system_id,),
    ).fetchall()
    top_attackers_list = [dict(r) for r in top_attackers]

    # Determine danger level
    total_kills = kill_row["total_kills"] if kill_row else 0
    if total_kills >= 50:
        danger_level = "extreme"
    elif total_kills >= 20:
        danger_level = "high"
    elif total_kills >= 5:
        danger_level = "moderate"
    elif total_kills > 0:
        danger_level = "low"
    else:
        danger_level = "minimal"

    stats = {
        "total_kills": total_kills,
        "unique_victims": kill_row["unique_victims"] if kill_row else 0,
        "unique_attackers": unique_attackers_row["cnt"] if unique_attackers_row else 0,
        "kills_24h": kill_row["kills_24h"] if kill_row else 0,
        "kills_7d": kill_row["kills_7d"] if kill_row else 0,
        "gate_transits": gate_row["cnt"] if gate_row else 0,
        "assembly_count": assembly_row["cnt"] if assembly_row else 0,
        "danger_level": danger_level,
        "top_attackers": top_attackers_list,
    }

    # Check cache
    eh = _event_hash({"system_id": system_id, "stats": stats})
    cached = _get_cached(db, system_id, "system_dossier", eh)
    if cached:
        return cached

    # Fallback to template if no API key
    if not settings.ANTHROPIC_API_KEY:
        content = _template_system_narrative(system_name, stats)
        _store_cache(db, system_id, "system_dossier", eh, content)
        return content

    # Generate with AI
    try:
        client = _get_client()
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            system=DOSSIER_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": SYSTEM_DOSSIER_USER.format(
                        system_name=system_name,
                        system_id=system_id,
                        kill_count=stats["total_kills"],
                        kills_24h=stats["kills_24h"],
                        kills_7d=stats["kills_7d"],
                        unique_attackers=stats["unique_attackers"],
                        unique_victims=stats["unique_victims"],
                        gate_transits=stats["gate_transits"],
                        danger_level=danger_level,
                        top_attackers_json=json.dumps(top_attackers_list, indent=2),
                        assembly_count=stats["assembly_count"],
                    ),
                }
            ],
        )
        content = msg.content[0].text
        _track_usage(msg, "system_dossier", system_id)
        _store_cache(db, system_id, "system_dossier", eh, content)
        logger.info("Generated system narrative for %s", system_id)
        return content
    except ValueError:
        logger.exception("System narrative generation error")
        return "System narrative temporarily unavailable."
    except Exception as e:
        logger.error("System narrative generation failed: %s", e)
        return _template_system_narrative(system_name, stats)


def generate_battle_report(events: list[dict]) -> dict:
    """Generate an AI battle report from a sequence of events."""
    if not events:
        return {"error": "No events provided"}

    eh = _event_hash(events)
    db = get_db()

    # Check cache using first event's entity as key
    cache_key = events[0].get("solar_system_id") or events[0].get("gate_id") or "battle"
    cached = _get_cached(db, cache_key, "battle", eh)
    if cached:
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            pass

    try:
        client = _get_client()
        clean_events = [{k: v for k, v in e.items() if k != "raw_json"} for e in events]

        duration = events[-1].get("timestamp", 0) - events[0].get("timestamp", 0)

        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=2048,
            system=BATTLE_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": BATTLE_USER.format(
                        event_count=len(events),
                        duration_seconds=duration,
                        timeline_json=json.dumps(clean_events, indent=2, default=str),
                    ),
                }
            ],
        )

        content = msg.content[0].text
        _track_usage(msg, "battle_report", cache_key)
        # Parse JSON from response
        try:
            report = json.loads(content)
        except json.JSONDecodeError:
            # Try extracting JSON block
            import re

            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                report = json.loads(match.group())
            else:
                return {"error": "Failed to parse battle report", "raw": content}

        _store_cache(db, cache_key, "battle", eh, json.dumps(report))
        logger.info("Generated battle report (%d events)", len(events))
        return report
    except ValueError:
        logger.exception("Battle report generation error")
        return {"error": "Battle report generation temporarily unavailable."}
    except Exception as e:
        logger.error("Battle report generation failed: %s", e)
        return {"error": "Battle report generation temporarily unavailable."}
