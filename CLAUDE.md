# CLAUDE.md — witness

## Project Overview

The Living Memory of EVE Frontier — chain archaeology, AI intelligence, locator agent

## Current State

- **Version**: 0.1.0
- **Language**: Python
- **Files**: 107 across 6 languages
- **Lines**: 16,276

## Architecture

```
witness/
├── .github/
│   └── workflows/
├── backend/
│   ├── analysis/
│   ├── api/
│   ├── bot/
│   ├── core/
│   ├── db/
│   └── ingestion/
├── contracts/
│   └── src/
├── data/
├── docs/
├── frontend/
│   ├── public/
│   └── src/
├── scripts/
├── tests/
├── .env.example
├── .gitignore
├── CLAUDE.md
├── Dockerfile
├── README.md
├── docker-compose.yml
├── fly.toml
├── pyproject.toml
```

## Tech Stack

- **Language**: Python, TypeScript, CSS, JavaScript, HTML, Shell
- **Framework**: fastapi
- **Package Manager**: pip
- **Linters**: ruff
- **Formatters**: ruff
- **Test Frameworks**: pytest
- **Runtime**: Docker
- **CI/CD**: GitHub Actions

## Coding Standards

- **Naming**: snake_case
- **Quote Style**: double quotes
- **Type Hints**: present
- **Imports**: absolute
- **Path Handling**: pathlib
- **Line Length (p95)**: 75 characters

## Common Commands

```bash
# test
pytest tests/ -v
# lint
ruff check backend/ tests/
# format
ruff format backend/ tests/
# coverage
pytest --cov=backend --cov-fail-under=80 tests/

# docker CMD
["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Critical Rules

- POLLER MUST NEVER CRASH — all errors logged, never raised
- Schema confirmed against blockchain-gateway-stillness.live.tech.evefrontier.com v2 API (2026-03-07)
- API returns paginated results with {data: [], metadata: {total, limit, offset}}
- Killmails are FIRST-CLASS data — only durable positional signal post-coordinate-privacy
- Coordinates are hackathon-only — don't build core features on them
- Cache AI narratives — same entity + same event hash = cached response
- Attacker data can be strings OR dicts with "address" key — always normalize with _extract_ids()
- SQLite check_same_thread=False required for FastAPI lifespan threading

## Data Flow

```
World API (polling) → Poller → SQLite → Entity Resolver → Naming Engine
                                   ↓              ↓              ↓
                              FastAPI API    AI Narratives   Story Feed
                                   ↓              ↓              ↓
                              Dashboard     Discord Bot     Webhook Alerts
                                   ↓
                         Reputation → On-Chain (WatcherSystem.sol)
```

## Anti-Patterns (Do NOT Do)

- Do NOT commit secrets, API keys, or credentials
- Do NOT skip writing tests for new code
- Do NOT hardcode secrets in Dockerfiles — use environment variables
- Do NOT use `latest` tag — pin specific versions
- Do NOT use `os.path` — use `pathlib.Path` everywhere
- Do NOT use bare `except:` — catch specific exceptions
- Do NOT use mutable default arguments
- Do NOT use `print()` for logging — use the `logging` module
- Do NOT use `any` type — define proper type interfaces
- Do NOT use `var` — use `const` or `let`
- Do NOT use synchronous database calls in async endpoints
- Do NOT return raw dicts — use Pydantic response models

## Dependencies

### Core
- fastapi
- uvicorn

### Dev
- pytest
- pytest-asyncio
- pytest-cov
- respx
- ruff

## Domain Context

### Key Models/Classes
- `BattleReportRequest`
- `CorpProfile`
- `EntityDossier`
- `Fingerprint`
- `Hotzone`
- `KillEdge`
- `KillGraphNode`
- `ProfileActions`
- `ReputationScore`
- `RouteProfile`
- `Settings`
- `SocialProfile`
- `StreakInfo`
- `SubscribeRequest`
- `TemporalProfile`

### Domain Terms
- AI
- Alt Detection
- Assembly Guide
- Behavioral Fingerprints
- CSS
- Chain Archaeology
- Chain Economy
- Chain Trust Scoring
- Character Titles
- Combat Honor

### API Endpoints
- `/assemblies`
- `/assemblies/list`
- `/battle-report`
- `/corp/{corp_id}`
- `/corps`
- `/corps/rivalries`
- `/entities`
- `/entity/{entity_id}`
- `/entity/{entity_id}/fingerprint`
- `/entity/{entity_id}/narrative`
- `/entity/{entity_id}/reputation`
- `/entity/{entity_id}/streak`
- `/entity/{entity_id}/timeline`
- `/feed`
- `/fingerprint/compare`

### Enums/Constants
- `ANTHROPIC_API_KEY`
- `BASE`
- `BATTLE_SYSTEM`
- `BATTLE_USER`
- `DISCORD_WEBHOOK_URL`
- `DOSSIER_SYSTEM`
- `DOSSIER_USER`
- `SCHEMA`
- `WATCHER_OWNER_ADDRESS`

## AI Skills

**Installed**: 117 skills in `~/.claude/skills/`
- `a11y`, `accessibility-checker`, `agent-teams-orchestrator`, `align-debug`, `api-client`, `api-docs`, `api-tester`, `apple-dev-best-practices`, `arch`, `backup`, `build`, `changelog`, `ci`, `cicd-pipeline`, `code-builder`
- ... and 102 more

**Recommended bundles**: `api-integration`, `full-stack-dev`

**Recommended skills** (not yet installed):
- `api-integration`
- `full-stack-dev`

## Git Conventions

- Commit messages: Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`)
- Branch naming: `feat/description`, `fix/description`
- Run tests before committing
