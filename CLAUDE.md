# Witness — The Living Memory of EVE Frontier

## What This Is
Chain archaeology + AI intelligence + locator agent for EVE Frontier.
Free lore layer (entity dossiers, story feed, titles) + paid Oracle layer (standing watches, behavioral fingerprinting, alerts).

## Architecture
- Backend: FastAPI + uvicorn, Python 3.11+
- Database: SQLite WAL + FTS5
- Ingestion: Polling EVE Frontier World API
- AI: Anthropic API for narrative generation
- Bot: discord.py for slash commands + webhook alerts
- Frontend: React + Tailwind (Week 3)
- Deployment: Single VPS (Hetzner/DO)

## Critical Rules
- POLLER MUST NEVER CRASH — all errors logged, never raised
- Run scripts/explore_api.py BEFORE changing any schema
- Schema field names are PLACEHOLDERS until confirmed against live API
- Killmails are FIRST-CLASS data — only durable positional signal post-coordinate-privacy
- Coordinates are hackathon-only — don't build core features on them
- Cache AI narratives — same entity + same event hash = cached response

## Data Flow
```
World API (polling) → Poller → SQLite → Entity Resolver → Naming Engine
                                   ↓              ↓              ↓
                              FastAPI API    AI Narratives   Story Feed
                                   ↓              ↓              ↓
                              Dashboard     Discord Bot     Webhook Alerts
```

## Key Decisions
- SQLite over Postgres: 3-week hackathon, single writer, read-heavy
- Polling over WebSocket: guaranteed to work, optimize later
- Discord bot as primary interface: zero friction, corps already there
- Entity-centric not player-centric: lore engine, not surveillance tool
- Free lore + paid Oracle: community adoption drives votes, intel drives revenue

## API Status
- Sandbox (Nova) is OFFLINE — decommissioned pre-Sui migration
- Live API available March 11 when hackathon server opens
- Confirm base URL + field names day 1 with explore_api.py

## Hackathon Timeline
- Pre-March 11: Scaffold, API explorer, DB schema, poller skeleton
- Week 1 (Mar 11-17): Live data flowing, entity resolver, basic stats
- Week 2 (Mar 18-24): AI narratives, naming engine, story feed, Discord bot
- Week 3 (Mar 25-31): React dashboard, polish, demo video
