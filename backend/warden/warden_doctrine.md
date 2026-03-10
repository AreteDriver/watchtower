# Warden Doctrine — Definition of Better

> Human-authored. The Warden may NEVER modify this file.
> This is the hard constraint on what the autonomous loop considers "better."

## Purpose

The Warden generates threat hypotheses from on-chain and game data,
tests them against evidence, and commits findings to the audit log.
It does NOT take actions — it produces intelligence.

## What "Better" Means

A hypothesis is BETTER if it:

1. **Identifies a real threat** — a pattern in killmails, gate transits, feral AI escalation,
   or scan results that correlates with player loss or zone danger.
2. **Is falsifiable** — it can be tested against the data we have.
3. **Has predictive value** — it says something about what will happen next,
   not just what already happened.
4. **Is actionable** — a player can do something with this information
   (avoid a zone, pre-position clones, scan a blind spot).

## What "Better" Does NOT Mean

- More hypotheses is not better. Fewer, higher-confidence findings win.
- Novel is not better. A boring hypothesis that saves a clone is better
  than an interesting one that doesn't.
- Complex is not better. "Zone X has escalating feral AI and hasn't been
  scanned in 40 minutes" is a better finding than a 5-variable correlation.

## Hypothesis Categories

### THREAT (high priority)
- Kill clusters forming in specific systems
- Feral AI escalation patterns (dormant → active → evolved → critical)
- Hostile entity movement patterns (gate transit sequences)
- Blind spots expanding (scan coverage gaps)

### LOGISTICS (medium priority)
- Clone reserve depletion trends
- Manufacturing bottlenecks (queue depth vs completion rate)
- Supply line vulnerability (assemblies in high-threat zones)

### INTEL (standard priority)
- New entity behavioral patterns (hunting routes, time preferences)
- Corp activity shifts (new territory, retreat patterns)
- Crown distribution anomalies

## Constraints

- **Max iterations per session**: Configurable, default 10
- **Max session duration**: Configurable, default 24 hours
- **LLM budget**: Max 20 API calls per session (narrative enrichment only)
- **Read-only**: Warden NEVER writes to game state or blockchain
- **Audit**: Every hypothesis + evaluation written to `warden_audit.jsonl`
- **Operator notification**: Any THREAT-category finding with confidence > 0.8
  fires a Discord webhook
- **No hallucination**: If data is insufficient, say so. Don't speculate.

## Evaluation Criteria

Score each hypothesis 0.0–1.0 on:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Evidence  | 0.35   | How much data supports this? |
| Recency   | 0.25   | How fresh is the evidence? |
| Impact    | 0.25   | How much damage if true? |
| Novelty   | 0.15   | Is this new information? |

**Composite score** = weighted sum. Commit if >= 0.5, discard if < 0.5.
