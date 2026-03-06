"""Discord bot slash commands — the primary player interface."""

import json
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from backend.analysis.entity_resolver import resolve_entity
from backend.analysis.naming_engine import refresh_all_titles
from backend.analysis.narrative import generate_dossier_narrative
from backend.analysis.oracle import check_watches
from backend.analysis.story_feed import generate_feed_items
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("bot")


class WitnessBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.tree.add_command(locate)
        self.tree.add_command(history)
        self.tree.add_command(watch)
        self.tree.add_command(unwatch)
        self.tree.add_command(feed)
        self.tree.add_command(opsec)
        self.tree.add_command(leaderboard)
        await self.tree.sync()
        logger.info("Slash commands synced")

        # Start background tasks
        self.oracle_loop.start()
        self.feed_loop.start()
        self.title_loop.start()

    @tasks.loop(minutes=1)
    async def oracle_loop(self):
        try:
            await check_watches()
        except Exception as e:
            logger.error(f"Oracle loop error: {e}")

    @tasks.loop(minutes=5)
    async def feed_loop(self):
        try:
            generate_feed_items()
        except Exception as e:
            logger.error(f"Feed loop error: {e}")

    @tasks.loop(hours=1)
    async def title_loop(self):
        try:
            db = get_db()
            count = refresh_all_titles(db)
            if count:
                logger.info(f"Refreshed {count} titles")
        except Exception as e:
            logger.error(f"Title loop error: {e}")

    async def on_ready(self):
        logger.info(f"Witness bot online as {self.user}")


# --- Slash Commands ---


@app_commands.command(name="locate", description="Look up any entity — gate, character, corp")
@app_commands.describe(entity_id="Entity ID or name to look up")
async def locate(interaction: discord.Interaction, entity_id: str):
    await interaction.response.defer()
    db = get_db()

    # Try exact match first, then search
    dossier = resolve_entity(db, entity_id)
    if not dossier:
        # Search by name
        row = db.execute(
            "SELECT entity_id FROM entities WHERE display_name LIKE ? LIMIT 1",
            (f"%{entity_id}%",),
        ).fetchone()
        if row:
            dossier = resolve_entity(db, row["entity_id"])

    if not dossier:
        await interaction.followup.send(f"Entity `{entity_id}` not found.")
        return

    d = dossier.to_dict()
    title_str = f' "{d["titles"][0]}"' if d["titles"] else ""

    embed = discord.Embed(
        title=f"{d['display_name']}{title_str}",
        description=f"Type: {d['entity_type']} | ID: `{d['entity_id'][:20]}`",
        color=0xFF6600,
    )
    embed.add_field(name="Events", value=str(d["event_count"]), inline=True)
    embed.add_field(name="Kills", value=str(d["kill_count"]), inline=True)
    embed.add_field(name="Deaths", value=str(d["death_count"]), inline=True)
    embed.add_field(name="Gates", value=str(d["gate_count"]), inline=True)

    if d["danger_rating"] != "unknown":
        embed.add_field(name="Danger", value=d["danger_rating"].upper(), inline=True)
    if d["unique_pilots"]:
        embed.add_field(name="Unique Pilots", value=str(d["unique_pilots"]), inline=True)
    if d["associated_corps"]:
        embed.add_field(
            name="Associated Corps",
            value="\n".join(c[:16] for c in d["associated_corps"][:5]),
            inline=False,
        )
    if d["titles"]:
        embed.add_field(name="Titles", value=", ".join(d["titles"]), inline=False)

    embed.set_footer(text="Witness — The Living Memory of EVE Frontier")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="history", description="AI-generated narrative for an entity")
@app_commands.describe(entity_id="Entity ID to analyze")
async def history(interaction: discord.Interaction, entity_id: str):
    await interaction.response.defer()
    narrative = generate_dossier_narrative(entity_id)

    embed = discord.Embed(
        title=f"Dossier: {entity_id[:20]}",
        description=narrative[:4000],
        color=0xFF6600,
    )
    embed.set_footer(text="Witness — AI-generated from on-chain evidence")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="watch", description="Set a standing intelligence watch")
@app_commands.describe(
    watch_type="Type: entity_movement, gate_traffic_spike, killmail_proximity, hostile_sighting",
    target_id="Entity/gate/system ID to watch",
    webhook_url="Discord webhook URL for alerts (optional, uses channel if not set)",
)
async def watch(
    interaction: discord.Interaction,
    watch_type: str,
    target_id: str,
    webhook_url: str = "",
):
    valid_types = {
        "entity_movement",
        "gate_traffic_spike",
        "killmail_proximity",
        "hostile_sighting",
    }
    if watch_type not in valid_types:
        await interaction.response.send_message(
            f"Invalid type. Choose from: {', '.join(valid_types)}", ephemeral=True
        )
        return

    db = get_db()
    db.execute(
        """INSERT INTO watches (user_id, watch_type, target_id, conditions, webhook_url, channel_id)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            str(interaction.user.id),
            watch_type,
            target_id,
            json.dumps({"lookback_seconds": 300}),
            webhook_url,
            str(interaction.channel_id),
        ),
    )
    db.commit()

    await interaction.response.send_message(
        f"Watch set: **{watch_type}** on `{target_id[:20]}`\n"
        f"You'll be alerted when conditions trigger.",
        ephemeral=True,
    )


@app_commands.command(name="unwatch", description="Remove a standing watch")
@app_commands.describe(target_id="Entity ID to stop watching")
async def unwatch(interaction: discord.Interaction, target_id: str):
    db = get_db()
    db.execute(
        "UPDATE watches SET active = 0 WHERE user_id = ? AND target_id = ? AND active = 1",
        (str(interaction.user.id), target_id),
    )
    db.commit()
    await interaction.response.send_message(f"Watch removed for `{target_id[:20]}`", ephemeral=True)


@app_commands.command(name="feed", description="Show recent story feed items")
@app_commands.describe(count="Number of items (default 5)")
async def feed(interaction: discord.Interaction, count: int = 5):
    count = min(count, 10)
    db = get_db()
    rows = db.execute(
        "SELECT * FROM story_feed ORDER BY timestamp DESC LIMIT ?", (count,)
    ).fetchall()

    if not rows:
        await interaction.response.send_message("No stories yet. Check back once data is flowing.")
        return

    lines = []
    for r in rows:
        age = int(time.time()) - r["timestamp"]
        if age < 3600:
            age_str = f"{age // 60}m ago"
        elif age < 86400:
            age_str = f"{age // 3600}h ago"
        else:
            age_str = f"{age // 86400}d ago"
        lines.append(f"**[{age_str}]** {r['headline']}")

    embed = discord.Embed(
        title="Witness Story Feed",
        description="\n\n".join(lines),
        color=0x00FF88,
    )
    embed.set_footer(text="Witness — The Living Memory of EVE Frontier")
    await interaction.response.send_message(embed=embed)


@app_commands.command(name="opsec", description="Check your corp's operational security score")
@app_commands.describe(corp_id="Your corp ID")
async def opsec(interaction: discord.Interaction, corp_id: str):
    await interaction.response.defer()
    db = get_db()

    # Basic OPSEC scoring based on behavioral predictability
    gate_events = db.execute(
        """SELECT character_id, gate_id, timestamp FROM gate_events
           WHERE corp_id = ? ORDER BY timestamp DESC LIMIT 500""",
        (corp_id,),
    ).fetchall()

    if len(gate_events) < 20:
        await interaction.followup.send(
            "Not enough data for OPSEC score. "
            f"Need at least 20 gate events, have {len(gate_events)}."
        )
        return

    # Time-of-day concentration (higher = more predictable = worse OPSEC)
    hour_counts: dict[int, int] = {}
    for e in gate_events:
        hour = (e["timestamp"] % 86400) // 3600
        hour_counts[hour] = hour_counts.get(hour, 0) + 1

    total = sum(hour_counts.values())
    max_hour_pct = max(hour_counts.values()) / total * 100 if total else 0

    # Route repetition (same gate used repeatedly = predictable)
    gate_counts: dict[str, int] = {}
    for e in gate_events:
        gate_counts[e["gate_id"]] = gate_counts.get(e["gate_id"], 0) + 1
    max_gate_pct = max(gate_counts.values()) / total * 100 if total else 0

    # Unique gates used (more diversity = better OPSEC)
    gate_diversity = len(gate_counts)

    # Score: 0-100 where 100 is best OPSEC
    time_score = max(0, 100 - max_hour_pct * 2)  # Penalize time concentration
    route_score = max(0, 100 - max_gate_pct * 2)  # Penalize route repetition
    diversity_score = min(100, gate_diversity * 10)  # Reward gate diversity

    opsec_score = int((time_score + route_score + diversity_score) / 3)

    rating = (
        "EXCELLENT"
        if opsec_score >= 80
        else "GOOD"
        if opsec_score >= 60
        else "FAIR"
        if opsec_score >= 40
        else "POOR"
    )

    peak_hour = max(hour_counts, key=hour_counts.get)

    embed = discord.Embed(
        title=f"OPSEC Score: {corp_id[:16]}",
        description=f"**{opsec_score}/100** — {rating}",
        color=0x00FF88 if opsec_score >= 60 else 0xFFCC00 if opsec_score >= 40 else 0xFF0000,
    )
    embed.add_field(
        name="Time Predictability",
        value=f"{max_hour_pct:.0f}% in peak hour ({peak_hour}:00 UTC)",
        inline=False,
    )
    embed.add_field(
        name="Route Predictability",
        value=f"{max_gate_pct:.0f}% through top gate",
        inline=False,
    )
    embed.add_field(
        name="Gate Diversity",
        value=f"{gate_diversity} unique gates used",
        inline=False,
    )
    embed.set_footer(text="Witness Oracle — Counter-Intelligence Analysis")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="leaderboard", description="View top entities by category")
@app_commands.describe(
    category="Category: deadliest_gates, most_active_gates, top_killers, most_deaths, most_traveled"
)
async def leaderboard(interaction: discord.Interaction, category: str = "most_active_gates"):
    db = get_db()

    queries = {
        "deadliest_gates": ("Deadliest Gates", "entity_type = 'gate'", "kill_count DESC"),
        "most_active_gates": ("Most Active Gates", "entity_type = 'gate'", "event_count DESC"),
        "top_killers": (
            "Top Killers",
            "entity_type = 'character' AND kill_count > 0",
            "kill_count DESC",
        ),
        "most_deaths": (
            "Most Deaths",
            "entity_type = 'character' AND death_count > 0",
            "death_count DESC",
        ),
        "most_traveled": ("Most Traveled", "entity_type = 'character'", "gate_count DESC"),
    }

    if category not in queries:
        await interaction.response.send_message(
            f"Unknown category. Choose: {', '.join(queries.keys())}", ephemeral=True
        )
        return

    title, where, order = queries[category]
    rows = db.execute(
        f"SELECT entity_id, display_name, event_count, "
        f"kill_count, death_count, gate_count "
        f"FROM entities WHERE {where} "
        f"ORDER BY {order} LIMIT 10",
    ).fetchall()

    if not rows:
        await interaction.response.send_message("No data yet.")
        return

    lines = []
    for i, r in enumerate(rows, 1):
        name = r["display_name"] or r["entity_id"][:16]
        if "killer" in category or "deadliest" in category:
            stat = r["kill_count"]
        elif "death" in category:
            stat = r["death_count"]
        elif "traveled" in category:
            stat = r["gate_count"]
        else:
            stat = r["event_count"]
        lines.append(f"**{i}.** {name} — {stat}")

    embed = discord.Embed(
        title=f"Leaderboard: {title}",
        description="\n".join(lines),
        color=0xFF6600,
    )
    await interaction.response.send_message(embed=embed)


def run_bot():
    """Entry point for the Discord bot."""
    if not settings.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set — bot cannot start")
        return
    bot = WitnessBot()
    bot.run(settings.DISCORD_TOKEN)
