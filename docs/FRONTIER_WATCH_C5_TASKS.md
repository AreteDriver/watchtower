# FRONTIER WATCH — Cycle 5: Shroud of Fear
## Claude Code Task List
> Universe reset: March 11. Hackathon window: March 11–31.
> Read CLAUDE.md before any task. Never crash the poller.

---

## 1. UNIVERSE RESET CONTEXT

- [ ] Add `cycle` field to all DB tables (`cycle INT DEFAULT 5`)
- [ ] Add `reset_at` timestamp to schema — record when Cycle 5 began
- [ ] Build `/api/cycle` endpoint returning current cycle number, reset timestamp, and days elapsed
- [ ] Add cycle banner component to dashboard header: "CYCLE 5 // SHROUD OF FEAR // DAY {N}"
- [ ] Ensure poller flushes and re-seeds on universe reset detection (compare known epoch vs API epoch)

---

## 2. ORBITAL ZONES + FERAL AI

- [ ] Add `orbital_zones` table: `zone_id, name, coordinates, feral_ai_tier, last_scanned, threat_level`
- [ ] Poll Frontier World API for orbital zone state — confirm endpoint from sandbox explorer
- [ ] Add `feral_ai_events` table: `zone_id, event_type, severity, timestamp` — track AI evolution events
- [ ] Build `/api/orbital-zones` endpoint with threat_level filter param
- [ ] Build Orbital Zone panel on dashboard:
  - Zone list sorted by threat level (DORMANT / ACTIVE / EVOLVED / CRITICAL)
  - Feral AI tier indicator per zone (color-coded: green → amber → red → purple)
  - Last scan timestamp + staleness warning if >15 min old
  - "AI EVOLVED" alert badge when tier increases between polls
- [ ] Wire feral AI tier escalation to Discord webhook alert: `⚠ FERAL AI EVOLVED — [Zone] reached Tier {N}`

---

## 3. VOID SCANNING INTEL

- [ ] Add `scans` table: `scan_id, zone_id, scanner_id, result_type, result_data JSON, scanned_at`
- [ ] Add `scan_intel` table: `zone_id, threat_signature, anomaly_type, confidence, reported_at`
- [ ] Build `/api/scans` endpoint — recent scans by zone, filterable by result_type
- [ ] Build Void Scan Feed panel:
  - Live feed of scan results (newest first, auto-scrolling)
  - Result type badges: CLEAR / ANOMALY / HOSTILE / UNKNOWN
  - Confidence % indicator per scan
  - "SCAN BEFORE YOU MOVE" warning banner on any zone with HOSTILE result in last 30 min
- [ ] Add scan staleness logic: zones not scanned in >20 min flagged as BLIND SPOT in UI
- [ ] Wire HOSTILE scan result to Discord webhook: `🔴 HOSTILE DETECTED — [Zone] scan by [Character]`

---

## 4. CLONE MANUFACTURING

- [ ] Add `clones` table: `clone_id, owner_id, blueprint_id, status, manufactured_at, location_zone_id`
- [ ] Add `clone_blueprints` table: `blueprint_id, name, tier, materials JSON, manufacture_time_sec`
- [ ] Poll World API for clone manufacturing activity — confirm endpoint
- [ ] Build `/api/clones` endpoint: active clones by corp, manufacturing queue, blueprint inventory
- [ ] Build Clone Status panel:
  - Corp clone count by tier
  - Active manufacturing queue with ETA
  - Blueprint inventory list
  - "LOW CLONE RESERVE" alert if active clones < configurable threshold (default: 5)
- [ ] Wire low clone alert to Discord: `⚠ CLONE RESERVE LOW — {N} active clones remaining`

---

## 5. CROWNS / IDENTITY

- [ ] Add `crowns` table: `crown_id, character_id, crown_type, attributes JSON, equipped_at, chain_tx_id`
- [ ] Index Crown data from Sui chain via MUD Indexer — confirm table name from Pyrope Explorer
- [ ] Build `/api/crowns` endpoint: corp member Crown roster, Crown type breakdown
- [ ] Build Identity/Crown panel:
  - Corp member list with equipped Crown type displayed
  - Crown type distribution chart (recharts pie or bar)
  - Members with no Crown flagged (unidentified / new)
  - Crown change events feed (member equipped/changed Crown)
- [ ] No Discord alert needed for Crown changes — informational only

---

## 6. BACKEND — NEW ENDPOINTS SUMMARY

All endpoints must return `{ cycle: 5, reset_at: "...", data: [...] }` envelope.

```
GET /api/cycle
GET /api/orbital-zones?threat_level=CRITICAL
GET /api/orbital-zones/{zone_id}/history
GET /api/scans?zone_id=&since=
GET /api/scans/feed
GET /api/clones?corp_id=
GET /api/clones/queue
GET /api/crowns?corp_id=
GET /api/crowns/roster
```

---

## 7. DISCORD ALERT WIRING

Extend `notifier.py` with these new alert types:

| Event | Trigger | Message |
|-------|---------|---------|
| Feral AI Evolved | tier increases | `⚠ FERAL AI EVOLVED — [Zone] Tier {N}` |
| Hostile Scan | scan result = HOSTILE | `🔴 HOSTILE DETECTED — [Zone]` |
| Blind Spot | zone unscan > 20 min | `👁 BLIND SPOT — [Zone] unseen for {N}m` |
| Clone Reserve Low | clones < threshold | `⚠ CLONE RESERVE LOW — {N} remaining` |
| AI Critical | tier = CRITICAL | `🚨 CRITICAL FERAL AI — [Zone] requires immediate response` |

---

## 8. SCHEMA MIGRATION

Run before any new poller code:

```sql
ALTER TABLE killmails ADD COLUMN cycle INT DEFAULT 5;
ALTER TABLE gate_events ADD COLUMN cycle INT DEFAULT 5;
ALTER TABLE storage_snapshots ADD COLUMN cycle INT DEFAULT 5;

CREATE TABLE IF NOT EXISTS orbital_zones ( ... );
CREATE TABLE IF NOT EXISTS feral_ai_events ( ... );
CREATE TABLE IF NOT EXISTS scans ( ... );
CREATE TABLE IF NOT EXISTS scan_intel ( ... );
CREATE TABLE IF NOT EXISTS clones ( ... );
CREATE TABLE IF NOT EXISTS clone_blueprints ( ... );
CREATE TABLE IF NOT EXISTS crowns ( ... );
```

Full `CREATE TABLE` statements to be generated after running `explore_sandbox.py` to confirm real API field names.

---

## 9. FRONTEND PANELS — LAYOUT PRIORITY

Add these panels to the existing dashboard in this order (highest hackathon impact first):

1. **Cycle Banner** — always visible, header strip
2. **Orbital Zones** — primary threat view, above the fold
3. **Void Scan Feed** — live intel stream, sidebar
4. **Clone Status** — corp readiness indicator
5. **Crown Roster** — identity panel, lower priority

---

## NOTES FOR CLAUDE CODE

- Run `explore_sandbox.py` first on any new table before writing schema
- All new poller loops follow same pattern as `poller.py` — never raise, always log
- `threat_level` is derived, not stored — compute from feral_ai_tier at query time
- Coordinate fields: include in schema but mark `-- HIDDEN POST-CYCLE` in comments
- Killmails remain the primary positional signal — do not deprioritize killmail ingestion
- Test Discord webhooks with `--dry-run` flag before live deployment
