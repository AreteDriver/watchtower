"""Batch-publish WatchTower reputation scores on-chain via Sui CLI.

Fetches computed reputation scores from the WatchTower API,
maps entity IDs to deterministic Sui addresses, and calls the
reputation.publish_score() Move function for each entity.

Usage:
    python scripts/publish_reputation.py [--dry-run]
"""

import hashlib
import json
import subprocess
import sys
import time
import urllib.request

# WatchTower API
API_BASE = "https://watchtower-evefrontier.fly.dev/api"

# Sui contract addresses (from Published.toml / hackathon submission)
PACKAGE_ID = "0x84f41e934e6612a160425996941e2fb80fe66fd59134e4184708812156d116c7"
ORACLE_CAP = "0x38cb4c7854ff604fb3cc1d410efab46d5710adea30e257d6f30f7b9b80378cf3"
REGISTRY = "0x01fd19b403e76d744c55be8cf559a9c53fb5ce743ecc82aa6d77d59b2454d3e6"

# Titles contract
TITLE_ORACLE_CAP = "0x3e70894a8df1be9a50fdf394cca2b86df616bbb36a0f381b331764ace2888df3"
TITLE_REGISTRY = "0x027d7fb9b17a2e8745ff11e2f64def8825d46564d52d7c9c64c9fa20f79f6c7a"

SUI_CLI = "/home/arete/sui-bin/sui"


def entity_to_address(entity_id: str) -> str:
    """Deterministic mapping: entity_id -> 0x-prefixed 64-char hex address."""
    h = hashlib.sha256(f"watchtower:{entity_id}".encode()).hexdigest()
    return f"0x{h}"


def fetch_json(path: str) -> dict:
    """Fetch JSON from WatchTower API."""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_entities() -> list[dict]:
    """Get all character entities."""
    data = fetch_json("/entities?limit=100&entity_type=character")
    return data.get("entities", [])


def fetch_reputation(entity_id: str) -> dict | None:
    """Get reputation score for an entity."""
    try:
        return fetch_json(f"/entity/{entity_id}/reputation")
    except Exception:
        return None


def fetch_titles(entity_id: str) -> list[str]:
    """Get earned titles for an entity."""
    try:
        data = fetch_json(f"/entity/{entity_id}")
        return data.get("titles", [])
    except Exception:
        return []


def publish_score(address: str, rep: dict, dry_run: bool = False) -> bool:
    """Call reputation::publish_score on chain."""
    timestamp = str(int(time.time()))
    breakdown = rep.get("breakdown", {})

    cmd = [
        SUI_CLI, "client", "call",
        "--package", PACKAGE_ID,
        "--module", "reputation",
        "--function", "publish_score",
        "--args",
        ORACLE_CAP,
        REGISTRY,
        address,
        str(int(rep.get("trust_score", 50))),
        str(int(breakdown.get("combat_honor", 50))),
        str(int(breakdown.get("target_diversity", 50))),
        str(int(breakdown.get("reciprocity", 50))),
        str(int(breakdown.get("consistency", 50))),
        str(int(breakdown.get("community", 50))),
        str(int(breakdown.get("restraint", 50))),
        timestamp,
        "--gas-budget", "10000000",
        "--json",
    ]

    if dry_run:
        print(f"  [DRY RUN] {' '.join(cmd[-18:])}")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()[:200]}")
        return False

    # Parse digest from JSON output
    try:
        tx = json.loads(result.stdout)
        digest = tx.get("digest", "unknown")
        print(f"  TX: {digest}")
    except json.JSONDecodeError:
        print(f"  TX submitted (non-JSON output)")
    return True


def grant_title(address: str, title: str, dry_run: bool = False) -> bool:
    """Call titles::grant_title on chain."""
    cmd = [
        SUI_CLI, "client", "call",
        "--package", PACKAGE_ID,
        "--module", "titles",
        "--function", "grant_title",
        "--args",
        TITLE_ORACLE_CAP,
        TITLE_REGISTRY,
        address,
        title,
        "--gas-budget", "10000000",
        "--json",
    ]

    if dry_run:
        print(f"  [DRY RUN] grant_title({title})")
        return True

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()[:200]}")
        return False

    try:
        tx = json.loads(result.stdout)
        digest = tx.get("digest", "unknown")
        print(f"  TX: {digest}")
    except json.JSONDecodeError:
        print(f"  TX submitted (non-JSON output)")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN MODE ===\n")

    # Fetch entities with combat activity
    print("Fetching entities...")
    entities = fetch_entities()
    combat_entities = [e for e in entities if e.get("kill_count", 0) > 0 or e.get("death_count", 0) > 0]
    print(f"Found {len(entities)} characters, {len(combat_entities)} with combat data\n")

    published = 0
    titles_granted = 0

    for entity in combat_entities:
        eid = entity["entity_id"]
        name = entity.get("display_name", eid)
        address = entity_to_address(eid)

        # Fetch reputation
        rep = fetch_reputation(eid)
        if not rep:
            print(f"SKIP {name} — no reputation data")
            continue

        trust = int(rep.get("trust_score", 0))
        rating = rep.get("rating", "unknown")
        print(f"{name} — trust={trust} ({rating}) → {address[:16]}...")

        if publish_score(address, rep, dry_run):
            published += 1

        # Fetch and grant titles
        titles = fetch_titles(eid)
        for title in titles:
            if grant_title(address, title, dry_run):
                titles_granted += 1

        # Small delay to avoid rate limits
        if not dry_run:
            time.sleep(0.5)

    print(f"\nPublished {published} reputation scores, {titles_granted} titles")
    if not dry_run:
        print(f"View on Suiscan: https://suiscan.xyz/testnet/account/{PACKAGE_ID}")


if __name__ == "__main__":
    main()
