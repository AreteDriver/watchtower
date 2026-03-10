# FRONTIER WATCH — Cycle 5: Shroud of Fear
## Claude Code Task List
> Universe reset: March 11. Hackathon window: March 11–31.
> Read CLAUDE.md before any task. Never crash the poller.

---

## STATUS: ALL C5 FEATURES IMPLEMENTED ✓

All 9 feature areas completed as of 2026-03-10.

---

## 1. UNIVERSE RESET CONTEXT ✓

- [x] Add `cycle` field to all DB tables (`cycle INT DEFAULT 5`)
- [x] Add `reset_at` timestamp to schema — record when Cycle 5 began
- [x] Build `/api/cycle` endpoint returning current cycle number, reset timestamp, and days elapsed
- [x] Add cycle banner component to dashboard header: "CYCLE 5 // SHROUD OF FEAR // DAY {N}"
- [x] Ensure poller flushes and re-seeds on universe reset detection (compare known epoch vs API epoch)

**Key files**: `backend/api/cycle5.py`, `frontend/src/components/CycleBanner.tsx`, `backend/ingestion/poller.py`

---

## 2. ORBITAL ZONES + FERAL AI ✓

- [x] Add `orbital_zones` table: zone_id, name, coordinates, feral_ai_tier, last_scanned, threat_level
- [x] Poll Frontier World API for orbital zone state
- [x] Add `feral_ai_events` table: zone_id, event_type, severity, timestamp
- [x] Build `/api/orbital-zones` endpoint with threat_level filter param
- [x] Build Orbital Zone panel on dashboard (zone list, threat level, staleness, AI evolved badge)
- [x] Wire feral AI tier escalation to Discord webhook alert

**Key files**: `backend/db/database.py`, `backend/api/cycle5.py`, `backend/analysis/oracle.py`, `frontend/src/components/OrbitalZones.tsx`

---

## 3. VOID SCANNING INTEL ✓

- [x] Add `scans` table: scan_id, zone_id, scanner_id, result_type, result_data JSON, scanned_at
- [x] Add `scan_intel` table: zone_id, threat_signature, anomaly_type, confidence, reported_at
- [x] Build `/api/scans` endpoint — recent scans by zone, filterable by result_type
- [x] Build Void Scan Feed panel (live feed, result badges, HOSTILE warning)
- [x] Add scan staleness logic: zones not scanned in >20 min flagged as BLIND SPOT
- [x] Wire HOSTILE scan result to Discord webhook

**Key files**: `backend/db/database.py`, `backend/api/cycle5.py`, `frontend/src/components/VoidScanFeed.tsx`

---

## 4. CLONE MANUFACTURING ✓

- [x] Add `clones` table: clone_id, owner_id, blueprint_id, status, manufactured_at, location_zone_id
- [x] Add `clone_blueprints` table: blueprint_id, name, tier, materials JSON, manufacture_time_sec
- [x] Poll World API for clone manufacturing activity
- [x] Build `/api/clones` endpoint: active clones by corp, manufacturing queue, blueprint inventory
- [x] Build Clone Status panel (clone count, queue with ETA, low reserve alert)
- [x] Wire low clone alert to Discord

**Key files**: `backend/db/database.py`, `backend/api/cycle5.py`, `frontend/src/components/CloneStatus.tsx`

---

## 5. CROWNS / IDENTITY ✓

- [x] Add `crowns` table: crown_id, character_id, crown_type, attributes JSON, equipped_at, chain_tx_id
- [x] Index Crown data from chain
- [x] Build `/api/crowns` endpoint: corp member Crown roster, Crown type breakdown
- [x] Build Identity/Crown panel (member list, type distribution, change feed)

**Key files**: `backend/db/database.py`, `backend/api/cycle5.py`, `frontend/src/components/CrownRoster.tsx`

---

## 6. BACKEND ENDPOINTS ✓

All return `{ cycle: 5, reset_at: "...", data: [...] }` envelope.

```
GET /api/cycle              ✓
GET /api/orbital-zones      ✓
GET /api/orbital-zones/{zone_id}/history  ✓
GET /api/scans              ✓
GET /api/scans/feed         ✓
GET /api/clones             ✓
GET /api/clones/queue       ✓
GET /api/crowns             ✓
GET /api/crowns/roster      ✓
```

---

## 7. DISCORD ALERT WIRING ✓

All 5 alert types implemented in `backend/analysis/oracle.py` with cooldown tracking.

| Event | Trigger | Status |
|-------|---------|--------|
| Feral AI Evolved | tier increases | ✓ |
| Hostile Scan | scan result = HOSTILE | ✓ |
| Blind Spot | zone unscan > 20 min | ✓ |
| Clone Reserve Low | clones < threshold | ✓ |
| AI Critical | tier = CRITICAL | ✓ |

---

## 8. SCHEMA MIGRATION ✓

All tables created in `backend/db/database.py`. Cycle fields on killmails, gate_events, storage_snapshots.

---

## 9. FRONTEND PANELS ✓

All 4 panels rendered in dedicated C5 tab in `frontend/src/App.tsx`:
1. **Cycle Banner** — header strip ✓
2. **Orbital Zones** — threat view ✓
3. **Void Scan Feed** — live intel ✓
4. **Clone Status** — corp readiness ✓
5. **Crown Roster** — identity panel ✓

---

## POST-RESET TODO (March 11+)

- [ ] Verify C5 API endpoint paths against live v2 API (current paths are pre-reset guesses)
- [ ] Run `explore_sandbox.py` against live tables to confirm field names
- [ ] Deploy to Fly.io after endpoint verification
- [ ] Test Discord webhooks with `--dry-run` flag before live deployment
