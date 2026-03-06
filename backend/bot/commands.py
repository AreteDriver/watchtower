"""Discord bot slash commands — the primary player interface."""

import json
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

from backend.analysis.entity_resolver import resolve_entity
from backend.analysis.fingerprint import build_fingerprint, compare_fingerprints
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
        self.tree.add_command(profile)
        self.tree.add_command(opsec)
        self.tree.add_command(leaderboard)
        self.tree.add_command(compare)
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


# --- Autocomplete ---


async def entity_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Autocomplete entity names from database."""
    if len(current) < 2:
        return []
    db = get_db()
    rows = db.execute(
        """SELECT entity_id, display_name, entity_type FROM entities
           WHERE entity_id LIKE ? OR display_name LIKE ?
           ORDER BY event_count DESC LIMIT 10""",
        (f"%{current}%", f"%{current}%"),
    ).fetchall()
    return [
        app_commands.Choice(
            name=f"[{r['entity_type'][:4].upper()}] {r['display_name'] or r['entity_id'][:20]}",
            value=r["entity_id"],
        )
        for r in rows
    ]


# --- Interactive Views ---


class ProfileActions(discord.ui.View):
    """Interactive buttons on profile results."""

    def __init__(self, entity_id: str):
        super().__init__(timeout=120)
        self.entity_id = entity_id

    @discord.ui.button(label="View Dossier", style=discord.ButtonStyle.primary, emoji="📜")
    async def view_dossier(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        narrative = generate_dossier_narrative(self.entity_id)
        embed = discord.Embed(
            title=f"Dossier: {self.entity_id[:20]}",
            description=narrative[:4000],
            color=0xFF6600,
        )
        embed.set_footer(text="Witness — AI-generated from on-chain evidence")
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="Set Watch", style=discord.ButtonStyle.secondary, emoji="👁️")
    async def set_watch(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = get_db()
        db.execute(
            """INSERT INTO watches
               (user_id, watch_type, target_id, conditions, webhook_url, channel_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                str(interaction.user.id),
                "entity_movement",
                self.entity_id,
                json.dumps({"lookback_seconds": 300}),
                "",
                str(interaction.channel_id),
            ),
        )
        db.commit()
        await interaction.response.send_message(
            f"Watch set on `{self.entity_id[:20]}` — you'll be alerted on movement.",
            ephemeral=True,
        )

    @discord.ui.button(label="OPSEC Report", style=discord.ButtonStyle.secondary, emoji="🛡️")
    async def opsec_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        db = get_db()
        fp = build_fingerprint(db, self.entity_id)
        if not fp or fp.event_count < 20:
            await interaction.followup.send("Not enough data for OPSEC analysis.", ephemeral=True)
            return
        color = 0x00FF88 if fp.opsec_score >= 60 else 0xFFCC00 if fp.opsec_score >= 40 else 0xFF0000
        embed = discord.Embed(
            title=f"OPSEC Score: {self.entity_id[:16]}",
            description=f"**{fp.opsec_score}/100** — {fp.opsec_rating}",
            color=color,
        )
        t = fp.temporal
        embed.add_field(
            name="Time Predictability",
            value=f"{t.peak_hour_pct:.0f}% in peak hour ({t.peak_hour:02d}:00 UTC)",
            inline=False,
        )
        r = fp.route
        embed.add_field(
            name="Route Predictability",
            value=f"{r.top_gate_pct:.0f}% through top gate",
            inline=False,
        )
        embed.set_footer(text="Witness Oracle — Counter-Intelligence Analysis")
        await interaction.followup.send(embed=embed)


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

    danger_colors = {
        "extreme": 0xFF0000,
        "high": 0xFF4400,
        "moderate": 0xFFCC00,
        "low": 0x00FF88,
    }
    color = danger_colors.get(d.get("danger_rating", ""), 0xFF6600)

    embed = discord.Embed(
        title=f"{d['display_name']}{title_str}",
        description=f"Type: {d['entity_type']} | ID: `{d['entity_id'][:20]}`",
        color=color,
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

    first_seen = d.get("first_seen", 0)
    last_seen = d.get("last_seen", 0)
    if first_seen and last_seen:
        embed.set_footer(
            text=(
                f"First seen: {time.strftime('%Y-%m-%d %H:%M', time.gmtime(first_seen))} UTC"
                f" | Last seen: {time.strftime('%Y-%m-%d %H:%M', time.gmtime(last_seen))} UTC"
            )
        )
    else:
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


@app_commands.command(
    name="profile",
    description="Full behavioral fingerprint for any entity",
)
@app_commands.describe(entity_id="Character or gate ID to profile")
async def profile(interaction: discord.Interaction, entity_id: str):
    await interaction.response.defer()
    db = get_db()
    fp = build_fingerprint(db, entity_id)
    if not fp:
        await interaction.followup.send(f"Entity `{entity_id[:20]}` not found.", ephemeral=True)
        return

    color = (
        0xFF0000
        if fp.threat.threat_level in ("extreme", "high")
        else 0xFFCC00
        if fp.threat.threat_level == "moderate"
        else 0x00FF88
    )
    embed = discord.Embed(
        title=f"Behavioral Profile: {entity_id[:20]}",
        description=(
            f"**OPSEC: {fp.opsec_score}/100** ({fp.opsec_rating})\n"
            f"**Threat: {fp.threat.threat_level.upper()}** "
            f"(K/D ratio: {fp.threat.kill_ratio:.2f})"
        ),
        color=color,
    )
    t = fp.temporal
    embed.add_field(
        name="Activity Pattern",
        value=(
            f"Peak: **{t.peak_hour:02d}:00 UTC**"
            f" ({t.peak_hour_pct:.0f}% of activity)\n"
            f"Active hours: {t.active_hours}/24\n"
            f"Predictability: {t.to_dict()['predictability']}"
        ),
        inline=False,
    )
    r = fp.route
    embed.add_field(
        name="Movement",
        value=(
            f"Unique gates: **{r.unique_gates}** "
            f"| Systems: **{r.unique_systems}**\n"
            f"Top gate: {r.top_gate[:16]}"
            f" ({r.top_gate_pct:.0f}%)\n"
            f"Route predictability: {r.to_dict()['predictability']}"
        ),
        inline=False,
    )
    if fp.entity_type == "character" and fp.social.unique_associates > 0:
        s = fp.social
        embed.add_field(
            name="Social",
            value=(
                f"Known associates: **{s.unique_associates}**\n"
                f"Top associate: {s.top_associate[:16]}"
                f" ({s.top_associate_count} co-transits)\n"
                f"Solo ratio: {s.solo_ratio:.0f}%"
            ),
            inline=False,
        )
    embed.set_footer(text="Witness — Behavioral Intelligence")
    await interaction.followup.send(embed=embed, view=ProfileActions(entity_id))


@app_commands.command(
    name="opsec",
    description="Check operational security score for an entity",
)
@app_commands.describe(entity_id="Character, corp, or gate ID")
async def opsec(interaction: discord.Interaction, entity_id: str):
    await interaction.response.defer()
    db = get_db()
    fp = build_fingerprint(db, entity_id)
    if not fp:
        await interaction.followup.send(f"Entity `{entity_id[:20]}` not found.", ephemeral=True)
        return

    if fp.event_count < 20:
        await interaction.followup.send(
            f"Not enough data for OPSEC score. Need at least 20 events, have {fp.event_count}."
        )
        return

    color = 0x00FF88 if fp.opsec_score >= 60 else 0xFFCC00 if fp.opsec_score >= 40 else 0xFF0000
    embed = discord.Embed(
        title=f"OPSEC Score: {entity_id[:16]}",
        description=f"**{fp.opsec_score}/100** — {fp.opsec_rating}",
        color=color,
    )
    t = fp.temporal
    embed.add_field(
        name="Time Predictability",
        value=(f"{t.peak_hour_pct:.0f}% in peak hour ({t.peak_hour:02d}:00 UTC)"),
        inline=False,
    )
    r = fp.route
    embed.add_field(
        name="Route Predictability",
        value=f"{r.top_gate_pct:.0f}% through top gate",
        inline=False,
    )
    embed.add_field(
        name="Gate Diversity",
        value=f"{r.unique_gates} unique gates used",
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


@app_commands.command(
    name="compare",
    description="Compare two entity fingerprints for alt detection",
)
@app_commands.describe(
    entity_1="First entity ID",
    entity_2="Second entity ID",
)
async def compare(interaction: discord.Interaction, entity_1: str, entity_2: str):
    await interaction.response.defer()
    db = get_db()
    fp1 = build_fingerprint(db, entity_1)
    fp2 = build_fingerprint(db, entity_2)
    if not fp1:
        await interaction.followup.send(f"Entity `{entity_1[:20]}` not found.", ephemeral=True)
        return
    if not fp2:
        await interaction.followup.send(f"Entity `{entity_2[:20]}` not found.", ephemeral=True)
        return

    result = compare_fingerprints(fp1, fp2)

    overall = result["overall_similarity"]
    color = 0xFF0000 if overall > 0.7 else 0xFFCC00 if overall > 0.4 else 0x00FF88

    embed = discord.Embed(
        title="Fingerprint Comparison",
        description=(
            f"`{entity_1[:16]}` vs `{entity_2[:16]}`\n**Overall Similarity: {overall:.1%}**"
        ),
        color=color,
    )
    embed.add_field(name="Temporal", value=f"{result['temporal_similarity']:.1%}", inline=True)
    embed.add_field(name="Route", value=f"{result['route_similarity']:.1%}", inline=True)
    embed.add_field(name="Social", value=f"{result['social_similarity']:.1%}", inline=True)

    verdicts = []
    if result["likely_alt"]:
        verdicts.append("⚠️ **LIKELY ALT ACCOUNT**")
    if result["likely_fleet_mate"]:
        verdicts.append("🤝 **LIKELY FLEET MATE**")
    if not verdicts:
        verdicts.append("✅ Distinct entities")

    embed.add_field(name="Verdict", value="\n".join(verdicts), inline=False)
    embed.set_footer(text="Witness — Behavioral Intelligence")
    await interaction.followup.send(embed=embed)


# --- Autocomplete bindings ---


@locate.autocomplete("entity_id")
async def locate_entity_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


@profile.autocomplete("entity_id")
async def profile_entity_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


@opsec.autocomplete("entity_id")
async def opsec_entity_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


@history.autocomplete("entity_id")
async def history_entity_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


@compare.autocomplete("entity_1")
async def compare_entity1_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


@compare.autocomplete("entity_2")
async def compare_entity2_autocomplete(interaction: discord.Interaction, current: str):
    return await entity_autocomplete(interaction, current)


def run_bot():
    """Entry point for the Discord bot."""
    if not settings.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not set — bot cannot start")
        return
    bot = WitnessBot()
    bot.run(settings.DISCORD_TOKEN)
