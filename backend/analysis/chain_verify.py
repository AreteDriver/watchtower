"""On-chain subscription verification via Sui GraphQL.

Supplementary check that queries SubscriptionCap objects owned by a wallet
directly from the Sui blockchain. DB remains the primary source of truth;
this provides an independent verification path for transparency.
"""

import time
from datetime import UTC, datetime

import httpx

from backend.core.logger import get_logger

logger = get_logger("chain_verify")

# Sui GraphQL endpoint (testnet)
SUI_GRAPHQL_URL = "https://graphql.testnet.sui.io/graphql"

# WatchTower package ID
WATCHTOWER_PKG = "0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca"

# SubscriptionCap type
SUBSCRIPTION_CAP_TYPE = f"{WATCHTOWER_PKG}::subscription::SubscriptionCap"

# GraphQL query for SubscriptionCap objects owned by a wallet
SUBSCRIPTION_CAP_QUERY = """
query FetchSubscriptionCaps($owner: SuiAddress!, $type: String!) {
  objects(
    filter: {
      owner: $owner
      type: $type
    }
  ) {
    nodes {
      asMoveObject {
        contents {
          json
        }
      }
    }
  }
}
"""

# Cache: {wallet_address: (result_dict_or_none, cached_at_timestamp)}
_chain_cache: dict[str, tuple[dict | None, float]] = {}
CACHE_TTL_SECONDS = 60

TIER_NAMES = {0: "free", 1: "scout", 2: "oracle", 3: "spymaster"}


async def verify_subscription_on_chain(wallet_address: str) -> dict | None:
    """Query Sui GraphQL for active SubscriptionCap objects owned by a wallet.

    Returns the highest-tier active subscription cap as a dict, or None if
    no active subscription exists on-chain. Caches results for 60 seconds.

    On any error, returns None (fail-open — DB is primary for hackathon).
    """
    now = time.time()

    # Check cache
    if wallet_address in _chain_cache:
        cached_result, cached_at = _chain_cache[wallet_address]
        if now - cached_at < CACHE_TTL_SECONDS:
            return cached_result

    try:
        result = await _query_subscription_caps(wallet_address)
        _chain_cache[wallet_address] = (result, now)
        return result
    except Exception:
        logger.exception("Chain verification failed for %s", wallet_address[:16])
        return None


async def _query_subscription_caps(wallet_address: str) -> dict | None:
    """Execute the GraphQL query and parse active SubscriptionCap objects."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SUI_GRAPHQL_URL,
            json={
                "query": SUBSCRIPTION_CAP_QUERY,
                "variables": {
                    "owner": wallet_address,
                    "type": SUBSCRIPTION_CAP_TYPE,
                },
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

    if "errors" in data:
        logger.error("Sui GraphQL errors during chain verify: %s", data["errors"])
        return None

    nodes = data.get("data", {}).get("objects", {}).get("nodes", [])
    if not nodes:
        return None

    now_ms = int(time.time() * 1000)
    best_cap: dict | None = None
    best_tier = 0

    for node in nodes:
        contents = node.get("asMoveObject", {}).get("contents", {}).get("json", {})
        if not contents:
            continue

        try:
            tier = int(contents.get("tier", 0))
            expires_at_ms = int(contents.get("expires_at_ms", 0))
        except (ValueError, TypeError):
            continue

        # Skip expired caps
        if expires_at_ms <= now_ms:
            continue

        # Track highest tier
        if tier > best_tier:
            best_tier = tier
            best_cap = {
                "tier": tier,
                "tier_name": TIER_NAMES.get(tier, "unknown"),
                "expires_at_ms": expires_at_ms,
                "expires_at": datetime.fromtimestamp(expires_at_ms / 1000, tz=UTC).isoformat(),
                "wallet": wallet_address,
            }

    return best_cap
