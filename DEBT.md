# Technical Debt Audit — Witness

**Project**: Witness — The Living Memory of EVE Frontier
**Audit Date**: 2026-03-08
**Auditor**: Claude Opus 4.6
**Hackathon Deadline**: March 11-31, 2026

---

## Executive Summary

**Overall Grade: B (7.2/10)**

Witness is an impressively complete hackathon project with strong test coverage (238 tests, 90% coverage), clean architecture, and a solid CI/CD pipeline. No critical security blockers were found. The main gaps are CORS wide-open for production, some f-string logging (minor CodeQL risk), missing `.pem`/`.key` in `.gitignore`, and the bot module (`commands.py` at 617 lines) being untested. For a hackathon submission, this is well above average.

---

## Category Scores

| Category | Score | Weight | Weighted |
|---|---|---|---|
| Security | 7/10 | blocker | no block |
| Correctness | 8/10 | 2x | 16 |
| Infrastructure | 8/10 | 2x | 16 |
| Maintainability | 7/10 | 1x | 7 |
| Documentation | 9/10 | 1x | 9 |
| Freshness | 8/10 | 0.5x | 4 |
| **Weighted Total** | | **6.5x** | **52** |
| **Weighted Average** | | | **8.0** |
| **Final (adjusted)** | | | **7.2** |

Adjustment: -0.8 for CORS wildcard in production + untested bot module (617 lines excluded from coverage).

---

## 1. Security (7/10)

### Findings

| Severity | Finding | Location |
|---|---|---|
| **MEDIUM** | CORS `allow_origins=["*"]` with `allow_credentials=True` | `backend/api/app.py:72-76` |
| **MEDIUM** | `.gitignore` missing `.pem`, `.key`, `.pem` file patterns | `.gitignore` |
| **LOW** | pip 24.0 has 2 CVEs (CVE-2025-8869, CVE-2026-1703) | `.venv/` |
| **LOW** | 7 f-string logging calls (CodeQL log-injection risk if user data flows in) | `commands.py`, `narrative.py`, `oracle.py` |
| **INFO** | `sk-test-key` in test file — harmless test mock | `tests/test_narrative.py` |

### What's Clean

- No hardcoded secrets in source (confirmed via regex scan)
- `.env` properly in `.gitignore`
- `contracts/.env.example` warns "NEVER commit the real .env"
- All credentials loaded via `pydantic-settings` with env prefix
- SQL queries use parameterized statements throughout (no injection)
- No command injection vectors found
- No SSRF — external calls only to configured `WORLD_API_BASE`
- `serve_frontend` has path traversal protection via `is_relative_to()` check
- CI has gitleaks, pip-audit, and CodeQL scanning
- `_ALLOWED_SORTS` frozenset prevents SQL injection in ORDER BY

### CORS Detail

```python
allow_origins=["*"],
allow_credentials=True,
```

This combination is problematic per the CORS spec. Browsers will block credentialed requests when origin is `*`. More importantly, for production deployment this should be locked to the actual frontend domain.

---

## 2. Correctness (8/10)

### Test Results

```
238 passed, 0 failed, 1 warning
Coverage: 89.83% (gate: 80%)
```

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | `backend/bot/commands.py` (617 lines) has zero tests | Excluded from coverage via `omit = ["backend/bot/*"]` |
| **MEDIUM** | `backend/api/app.py` at 48% coverage | Lifespan, intelligence loop, frontend serving untested |
| **LOW** | `backend/analysis/story_feed.py` at 76% coverage | Lines 210-275 uncovered |
| **LOW** | `backend/ingestion/poller.py` at 70% coverage | `run_poller()` loop and some error paths uncovered |
| **LOW** | `backend/analysis/naming_engine.py` at 76% coverage | Several title computation branches uncovered |
| **INFO** | `discord.py` deprecation warning: `audioop` removed in Python 3.13 | Test output |

### What's Solid

- 238 tests covering 16 test files
- All tests pass cleanly
- Good test isolation — each test file sets up its own in-memory SQLite
- `respx` used properly for HTTP mocking
- Entry point `uvicorn backend.api.app:app` verified in Dockerfile CMD
- Type hints on 73/151 functions (48%) — decent for hackathon speed
- All `async def` route handlers properly defined
- Pydantic models for request validation

---

## 3. Infrastructure (8/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | Dockerfile `pip install .` doesn't pin deps | No `requirements.txt` or lock file; builds may not be reproducible |
| **LOW** | Dockerfile missing `--no-cache-dir` on second install | Minor — but line 6 has it, COPY happens after |
| **LOW** | `docker-compose.yml` minimal — no healthcheck | Single service, no restart policy detail |
| **LOW** | `frontend/dist/` committed to git but also in `.gitignore` | Contradictory — dist exists in repo |
| **INFO** | `fly.toml` `min_machines_running = 0` — cold starts | Acceptable for hackathon |

### What's Solid

- CI has 3 jobs: lint (ruff check + format), test (matrix 3.11/3.12), security (pip-audit + gitleaks)
- CodeQL workflow with weekly schedule
- Dependabot for pip and GitHub Actions
- Fly.io config with persistent volume mount for SQLite
- `force_https = true` in fly.toml
- Docker image based on `python:3.12-slim` (good base)
- `data/` directory properly created in Dockerfile

---

## 4. Maintainability (7/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **MEDIUM** | `backend/bot/commands.py` — 617 lines (god file) | Should split into commands + views + helpers |
| **MEDIUM** | `backend/api/routes.py` — 464 lines | 28 endpoints in one file; could split by domain |
| **LOW** | `backend/analysis/fingerprint.py` — 489 lines | Complex but cohesive; borderline |
| **LOW** | Two Discord bot implementations | `bot/discord_bot.py` (256 lines) AND `bot/commands.py` (617 lines) |
| **LOW** | 7 f-string logging calls | Should use `%s` style per Python best practice |
| **INFO** | Global `_connection` singleton in `database.py` | Works for single-process, standard pattern for SQLite |

### What's Clean

- **Zero TODOs/FIXMEs/HACKs** in source code
- Clean module structure: `analysis/`, `api/`, `bot/`, `core/`, `db/`, `ingestion/`
- No dead code indicators (no commented-out blocks)
- Consistent naming: snake_case throughout Python
- `pathlib.Path` used everywhere (no `os.path`)
- No bare `except:` — all exception handlers are typed
- No `print()` calls in backend — proper logging throughout
- No mutable default arguments
- Proper `__init__.py` in all packages
- Imports well-organized (stdlib, third-party, local)

---

## 5. Documentation (9/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **LOW** | No CHANGELOG.md | Not critical for hackathon |
| **LOW** | No inline API docs (OpenAPI descriptions sparse) | FastAPI auto-docs work but could be richer |
| **INFO** | No LICENSE file (just "MIT" in README) | Should add LICENSE file for hackathon submission |

### What's Excellent

- **README.md** — 295 lines, comprehensive:
  - Live demo link
  - Architecture diagram (ASCII art)
  - Full API endpoint table (28 endpoints)
  - Quick start, Docker, configuration table
  - Feature breakdown with earned titles table
  - Discord bot command reference
  - Hackathon context and "why"
- **CLAUDE.md** — 5.2KB, well-structured project context
- **docs/ASSEMBLY_GUIDE.md** — Smart Assembly deployment guide
- **docs/DEMO_SCRIPT.md** — Hackathon presentation script
- **`.env.example`** — Clear with comments
- Docstrings on all major functions
- Module-level docstrings on all Python files
- Solidity contract fully documented with NatSpec

---

## 6. Freshness (8/10)

### Findings

| Severity | Finding | Detail |
|---|---|---|
| **INFO** | All 29 commits from March 6-7, 2026 | 2-day sprint, consistent velocity |
| **INFO** | `discord.py` `audioop` deprecation | Will break on Python 3.13 |

### Stack Versions

| Component | Version | Current | Status |
|---|---|---|---|
| Python | 3.12 | 3.12.x | Current |
| FastAPI | >=0.115.0 | 0.115.x | Current |
| React | 19.2.0 | 19.x | Current |
| Vite | 7.3.1 | 7.x | Current |
| Tailwind | 4.2.1 | 4.x | Current |
| TypeScript | 5.9.3 | 5.9.x | Current |
| Solidity | 0.8.24 | 0.8.x | Current |
| Pydantic | >=2.9.0 | 2.x | Current |
| discord.py | >=2.4.0 | 2.x | Current (with deprecation) |

All dependencies are modern and on latest major versions. No stale packages.

---

## Fix Recommendations (Ordered by ROI)

### High Impact / Low Effort (Do First)

| # | Fix | Time | Impact |
|---|---|---|---|
| 1 | Lock CORS to actual frontend domain (or `localhost` + fly.dev) | 5 min | Security |
| 2 | Add `.pem`, `.key`, `*.pem`, `*.key` to `.gitignore` | 2 min | Security |
| 3 | Add `LICENSE` file (MIT) | 2 min | Hackathon polish |
| 4 | Fix 7 f-string logger calls to use `%s` style | 10 min | CodeQL clean |
| 5 | Pin pip version in `.venv` (`pip install --upgrade pip>=26.0`) | 2 min | CVE fix |

### Medium Impact / Medium Effort

| # | Fix | Time | Impact |
|---|---|---|---|
| 6 | Add `requirements.txt` via `pip freeze` for reproducible Docker builds | 10 min | Infrastructure |
| 7 | Add healthcheck to `docker-compose.yml` | 5 min | Infrastructure |
| 8 | Remove `frontend/dist/` from git (it's in `.gitignore`) | 5 min | Cleanliness |
| 9 | Resolve dual bot files — `discord_bot.py` vs `commands.py` | 30 min | Maintainability |
| 10 | Add tests for `commands.py` or remove coverage omit | 2-4 hrs | Correctness |

### Low Impact / High Effort (Post-Hackathon)

| # | Fix | Time | Impact |
|---|---|---|---|
| 11 | Split `routes.py` into domain routers (entity, feed, intel, corp) | 1-2 hrs | Maintainability |
| 12 | Boost `story_feed.py` and `poller.py` coverage to 90%+ | 2-3 hrs | Correctness |
| 13 | Add rate limiting to API endpoints | 1-2 hrs | Security |
| 14 | Add OpenAPI descriptions to all endpoints | 1 hr | Documentation |
| 15 | Add type hints to remaining 78 functions | 2-3 hrs | Correctness |

---

## What's Done Well

1. **Test discipline** — 238 tests, 90% coverage, test matrix (3.11/3.12), clean pass
2. **Security posture** — No hardcoded secrets, parameterized SQL, gitleaks + CodeQL + pip-audit in CI
3. **Architecture** — Clean separation: ingestion -> analysis -> API -> presentation
4. **Resilience** — Poller designed to never crash; all errors logged, never raised
5. **Documentation** — README is hackathon-showcase quality with architecture diagrams
6. **Smart caching** — AI narrative cache by entity + event hash (avoids redundant API calls)
7. **Full stack** — Python backend + React frontend + Solidity contract + Discord bot + deployment config
8. **Modern stack** — All dependencies on latest versions, no legacy debt
9. **Zero TODOs** — No deferred work markers in codebase
10. **Dependency management** — Dependabot + CodeQL + pip-audit covering all angles

---

*Generated by technical debt audit. No code was modified during this audit.*
