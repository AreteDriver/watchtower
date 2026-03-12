# WatchTower — The Living Memory of EVE Frontier

> **Chain archaeology + AI intelligence + on-chain economy.**
> Every gate transit, every killmail, every entity on-chain — cataloged, analyzed, scored, enforced.
>
> *WatchTower doesn't just watch — it remembers, and the chain listens.*

**[Live Demo](https://watchtower-evefrontier.vercel.app/)** | [API Docs](#api-endpoints) | [Discord Bot](#discord-bot) | [Assembly Guide](docs/ASSEMBLY_GUIDE.md)

---

## Current Cycle Status

WatchTower's indexer migrated from World API to **Sui GraphQL** on March 12, 2026 — CCP's confirmed architecture direction for all dynamic data. Live data is actively accumulating.

- **Current cycle (Sui GraphQL):** 1,320+ characters · 18+ killmails · 500+ assemblies — and growing
- **Previous cycle (Stillness):** 36,085 entities fingerprinted · 4,795 killmails analyzed · 170 earned titles generated

---

## What is WatchTower?

WatchTower turns raw on-chain behavior into identity. Every entity that acts on the frontier leaves a trace. WatchTower finds the patterns in those traces and builds intelligence from them — who is this pilot, where do they operate, what have they earned, what is their reputation worth. No manual tagging. No self-reported data. The chain doesn't lie.

The chain never forgets. Neither does WatchTower.

---

## Features

### Chain Archaeology (Free)
- **Entity Dossiers** — Full profiles with stats, timelines, danger ratings
- **Behavioral Fingerprints** — Temporal patterns, route analysis, social networks, threat assessment, OPSEC scoring
- **Earned Titles** — Deterministic names from chain stats: "The Reaper" (50+ kills), "The Ghost" (30+ transits, zero combat), "The Meatgrinder" (20+ nearby kills on a gate)
- **Story Feed** — Auto-generated news: engagement clusters, streak milestones, new entity appearances, hunter milestones
- **Leaderboards** — Top killers, most deaths, deadliest gates, most traveled
- **Alt Detection** — Fingerprint comparison to identify likely alts and fleet mates
- **AI Narratives** — Entity dossiers and battle reports generated from chain data

### Tactical Intelligence
- **Kill Network** — Attacker→victim graph with vendetta detection (mutual kills between entities)
- **Danger Zones** — Solar systems ranked by kill density with time window filtering (24h/7d/30d/all)
- **Streak Tracker** — Kill streak tracking, momentum status (hot/active/cooling/dormant), active hunter board
- **Corp Intel** — Corporation combat rankings, member aggregation, inter-corp rivalry detection

### Reputation System
- **On-Chain Trust Scoring** — Every entity scored 0-100 across 6 dimensions:
  - **Combat Honor** — Clean kills vs ganking behavior
  - **Target Diversity** — Range of opponents (not farming the same pilot)
  - **Reciprocity** — Fair fights vs one-sided engagements
  - **Consistency** — Stable behavior over time (not erratic)
  - **Community** — Gate construction, assembly deployment, positive-sum actions
  - **Restraint** — Avoidance of excessive force, new player protection
- **Smart Assembly Gating** — Reputation scores flow back on-chain. Deployers can set thresholds: "deny docking if trust < 40"
- **Designed for Smart Contracts** — Scores structured for direct consumption by WatcherSystem.sol

### Real-Time Intelligence
- **Server-Sent Events** — Live push feed for kills, alerts, and system status
- **Live Ticker** — Dashboard shows real-time events as they happen (kills, alerts, status)
- **EVE SSO Login** — Verify character identity via CCP's OAuth2, cross-reference with on-chain data

### The Oracle (Intelligence Layer)
- **Standing Watches** — Monitor entities, gates, systems with Discord/webhook alerts
- **Movement Detection** — Know when a target transits any gate
- **Traffic Spike Alerts** — Unusual gate activity notifications
- **Killmail Proximity** — Instant notification when ships die in monitored systems

### On-Chain Economy
- **Smart Contract Subscriptions** — [WatcherSystem.sol](#smart-contract) (MUD v2 Solidity) manages three paid tiers via on-chain item transfer
- **Watcher Assembly Network** — Live tracker of deployed "The Watcher" Smart Assemblies across the frontier. Auto-updates from chain data. Shows online/offline status, system coverage, fleet health
- **Tier-Gated Access** — Backend verifies on-chain subscription status (5-min cache) and gates endpoints by tier

---

## Architecture

```
Sui GraphQL API (30s polling)
        ↓
   Indexer (Python/FastAPI)
   — KillmailCreatedEvent, CharacterCreatedEvent, AssemblyCreatedEvent, JumpEvent
   — normalizes and stores raw event data
        ↓
   SQLite WAL
        ↓
   ┌──────────┬───────────────┬───────────┬──────────┐
   ↓          ↓               ↓           ↓          ↓
 Entity    Naming        Story Feed   Kill Graph  Hotzones
 Resolver  Engine        + Streaks    + Vendettas  + Corps
   ↓          ↓               ↓           ↓          ↓
 Fingerprint  Earned        Auto-      Network    Danger
  Builder     Titles        News      Analysis    Zones
   ↓          ↓               ↓           ↓          ↓
   └──────────┴───────────┬───┼───────────┴──────────┘
                          ↓   ↓
                    Reputation Engine
                   (6-dimension scoring)
                          ↓
                     FastAPI API (33 endpoints)
                          ↓
                ┌─────────┼──────────┬──────────────┐
                ↓         ↓          ↓              ↓
           React SPA   Discord    Webhooks    WatcherSystem.sol
           (5 tabs,      Bot                  (MUD v2 contract)
          20 components)                            ↓
                                          Smart Assembly gating
                                         ("deny dock if trust < 40")
                                                    ↓
                                           ← back on-chain →
```

**The loop**: Data flows in from the chain → WatchTower analyzes and scores → reputation scores flow back on-chain via WatcherSystem.sol → Smart Assemblies enforce access based on trust → player behavior changes → new chain data flows in.

### Smart Contract

**WatcherSystem.sol** — MUD v2 Solidity contract deployed on-chain.

Three subscription tiers, paid via Smart Assembly inventory transfer (in-game items):

- **Scout** (7 days) — Behavioral fingerprints, reputation scores
- **Oracle** (7 days) — + AI narratives, standing watches, locator agent
- **Spymaster** (7 days) — + Alt detection, kill networks, battle reports

Subscription status is verified on-chain. The backend checks wallet subscription state with a 5-minute cache and gates endpoint access by tier.

### Data Sources
- **Dynamic data** (killmails, gate events, entity activity) — Sui GraphQL API (`graphql.testnet.sui.io`)
- **Static data** (typeIDs, system names) — World API (stillness)

### Tech Stack
- **Backend**: Python 3.12, FastAPI, SQLite WAL, Pydantic v2
- **Frontend**: React 19, Vite, Tailwind CSS v4, TypeScript strict
- **Intelligence**: Anthropic API (Claude) for narrative generation
- **On-Chain**: MUD v2, Solidity (WatcherSystem.sol), Sui Move (reputation oracle)
- **Bot**: Discord webhooks
- **Deployment**: Fly.io (backend), Vercel (frontend), Docker
- **Ingestion**: Never-crash poller with Sui GraphQL event subscription, error isolation
- **Tests**: 476 passing, 80%+ coverage

### Design Principles
1. **The poller must never crash** — all errors logged, never raised
2. **Killmails are first-class data** — the only durable positional signal
3. **Deterministic titles** — same data = same names, everyone sees the same thing
4. **Cache AI narratives** — same entity + same events = cached response
5. **Template fallback** — narratives work without API key via rule-based generation
6. **The chain loop** — data in → analysis → reputation → on-chain enforcement → behavioral change → new data

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/AreteDriver/watchtower.git
cd watchtower
pip install -e ".[dev]"

# Configure (optional — works without API keys)
cp .env.example .env

# Backfill historical data
python -m scripts.backfill

# Run
uvicorn backend.api.app:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up -d
# → http://localhost:8000
```

---

## API Endpoints

All endpoints under `/api/` prefix. 33 endpoints total.

**Entities**
- `GET /api/entities` — List entities (filter, sort, paginate)
- `GET /api/entity/{id}` — Full entity dossier
- `GET /api/entity/{id}/fingerprint` — Behavioral fingerprint (temporal, route, social, threat, OPSEC)
- `GET /api/entity/{id}/timeline` — Unified event timeline with delta analysis
- `GET /api/entity/{id}/narrative` — AI-generated or template dossier narrative
- `GET /api/entity/{id}/reputation` — Trust score (0-100) with 6-dimension breakdown
- `GET /api/entity/{id}/streak` — Kill streak and momentum data
- `GET /api/search?q=` — Search entities by name or address

**Intelligence**
- `GET /api/feed` — Story feed (auto-generated news)
- `GET /api/leaderboard/{category}` — Rankings: top_killers, most_deaths, most_traveled, deadliest_gates
- `GET /api/titles` — Entities with earned titles
- `GET /api/fingerprint/compare` — Compare two entity fingerprints (alt detection)
- `GET /api/kill-graph` — Kill network (who kills whom, vendettas)
- `POST /api/battle-report` — AI battle analysis from event sequence

**Tactical**
- `GET /api/hotzones` — Dangerous systems ranked by kill density
- `GET /api/hotzones/{system_id}` — System detail (hourly distribution, top victims)
- `GET /api/streaks` — Active hunters on kill streaks
- `GET /api/corps` — Corporation combat leaderboard
- `GET /api/corps/rivalries` — Inter-corporation rivalries
- `GET /api/corp/{id}` — Corporation profile (members, kills, systems)

**Economy & Assemblies**
- `GET /api/subscription/{wallet}` — Check on-chain subscription status and tier
- `POST /api/subscribe` — Initiate subscription (triggers on-chain verification)
- `GET /api/assemblies` — Watcher Assembly Network summary (coverage, fleet health)
- `GET /api/assemblies/list` — List deployed Watcher assemblies with online/offline status

**Auth & Real-Time**
- `GET /api/auth/eve/login` — EVE SSO authorization URL
- `GET /api/auth/eve/callback` — OAuth2 callback — exchange code for session
- `GET /api/auth/eve/me` — Current EVE character info (with on-chain cross-ref)
- `POST /api/auth/eve/logout` — Clear EVE SSO session
- `GET /api/events` — SSE stream (kills, alerts, status)
- `GET /api/events/status` — SSE connection status

**System**
- `GET /api/health` — Service health + table counts
- `POST /api/watches` — Create standing intelligence watch
- `DELETE /api/watches/{id}` — Remove watch

---

## Discord Bot

10 slash commands for in-game intelligence:

- `/watchtower <name>` — Entity lookup — stats, titles, threat level, OPSEC rating
- `/killfeed [count]` — Latest killmails with timestamps
- `/leaderboard <category>` — Top killers, most deaths, most traveled
- `/feed` — Recent story feed items
- `/compare <entity1> <entity2>` — Fingerprint comparison — alt detection
- `/locate <id>` — Full entity lookup with danger rating
- `/history <id>` — AI-generated narrative dossier
- `/profile <id>` — Full behavioral fingerprint
- `/opsec <id>` — OPSEC score analysis
- `/watch <type> <target>` — Set a standing intelligence watch
- `/unwatch <target>` — Remove a standing watch

Set `WATCHTOWER_DISCORD_TOKEN` to activate.

---

## Dashboard

React SPA with five tabs and 20 components:

- **Intelligence** — Search any entity, view fingerprint card (temporal/route/social/threat profiles), activity heatmap, event timeline, AI narrative, reputation score
- **Tactical** — Kill network graph, danger zone heatmap, active hunter streaks, corp combat rankings, assembly map
- **Compare** — Side-by-side fingerprint comparison with alt/fleet-mate detection
- **Feed & Rankings** — Live story feed + leaderboard with category switching
- **Account** — Wallet connection, EVE SSO identity, subscription management, standing watches

Live SSE ticker shows real-time kills, alerts, and system updates as they happen.

---

## Earned Titles

Deterministic titles computed from on-chain stats. Same data = same title for everyone.

**Character Titles**
- **The Reaper** — 50+ kills
- **The Hunter** — 20+ kills
- **The Pathfinder** — 50+ gate transits
- **The Wanderer** — 20+ gate transits
- **The Marked** — 10+ deaths
- **The Survivor** — 0 deaths, 50+ events
- **The Ghost** — 30+ transits, 0 kills, 0 deaths

**Gate Titles**
- **The Meatgrinder** — 20+ nearby killmails
- **The Bloodgate** — 10+ nearby killmails
- **The Highway** — 1000+ transits
- **The Vault Gate** — 50+ transits, 0 nearby kills
- **The Crossroads** — 100+ unique pilots

---

## Development

```bash
# Backend tests (476 passing, 80%+ coverage)
pytest tests/ -v

# Frontend tests
cd frontend && npx vitest run

# Lint
ruff check backend/ tests/ && ruff format backend/ tests/

# Coverage
pytest --cov=backend --cov-fail-under=80 tests/

# Seed demo data (for hackathon demos)
python scripts/seed_demo.py
```

---

## Configuration

- `WATCHTOWER_POLL_INTERVAL_SECONDS` — Polling interval (default: 30)
- `WATCHTOWER_DB_PATH` — SQLite database path (default: `data/watchtower.db`)
- `WATCHTOWER_ANTHROPIC_API_KEY` — Enables AI narratives (template fallback without)
- `WATCHTOWER_DISCORD_TOKEN` — Enables Discord bot
- `WATCHTOWER_DISCORD_WEBHOOK_URL` — Alert delivery webhook
- `WATCHTOWER_EVE_SSO_CLIENT_ID` — CCP EVE SSO application client ID
- `WATCHTOWER_EVE_SSO_SECRET_KEY` — CCP EVE SSO application secret
- `WATCHTOWER_EVE_SSO_CALLBACK_URL` — OAuth2 callback URL

---

## Hackathon

Built for the **EVE Frontier × Sui Hackathon** (March 2026).

**Category**: Community Tools / Intelligence

**Why WatchTower?** EVE Frontier generates permanent on-chain data but no tools exist to make sense of it. WatchTower turns raw blockchain events into actionable intelligence — who's dangerous, which gates are contested, when new players appear, and whether that pilot is an alt. With the reputation system and WatcherSystem.sol, intelligence flows back on-chain to enforce community standards through Smart Assembly access control.

The chain is the source of truth. WatchTower is the interpreter. And now, the enforcer.

---

## License

MIT
