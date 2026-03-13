"""SUI fiat-pegged pricing oracle."""

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter

from backend.core.logger import get_logger

logger = get_logger("pricing")

router = APIRouter()

TIERS = {
    "scout": {"usd_per_week": 4.99, "label": "Scout", "tier": 1},
    "oracle": {"usd_per_week": 9.99, "label": "Oracle", "tier": 2},
    "spymaster": {"usd_per_week": 19.99, "label": "Spymaster", "tier": 3},
}

CACHE_TTL_SECONDS = 60
STALE_THRESHOLD_SECONDS = 300  # 5 minutes
HARD_FALLBACK_PRICE = 3.00

_price_cache: dict = {"value": None, "fetched_at": None}


def _fetch_coingecko() -> float | None:
    try:
        r = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=sui&vs_currencies=usd",
            timeout=5,
        )
        r.raise_for_status()
        return r.json()["sui"]["usd"]
    except Exception as e:
        logger.warning("CoinGecko fetch failed: %s", e)
        return None


def _fetch_binance() -> float | None:
    try:
        r = httpx.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=SUIUSDT",
            timeout=5,
        )
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:
        logger.warning("Binance fetch failed: %s", e)
        return None


def get_sui_price() -> tuple[float, datetime, bool]:
    """Get current SUI/USD price. Returns (price, fetched_at, is_stale)."""
    now = datetime.now(tz=UTC)

    # Check cache
    if (
        _price_cache["value"] is not None
        and _price_cache["fetched_at"] is not None
        and (now - _price_cache["fetched_at"]).total_seconds() < CACHE_TTL_SECONDS
    ):
        is_stale = (now - _price_cache["fetched_at"]).total_seconds() > STALE_THRESHOLD_SECONDS
        return _price_cache["value"], _price_cache["fetched_at"], is_stale

    # Try CoinGecko first
    price = _fetch_coingecko()

    # Fallback to Binance
    if price is None:
        price = _fetch_binance()

    # Update cache if we got a fresh price
    if price is not None:
        _price_cache["value"] = price
        _price_cache["fetched_at"] = now
        return price, now, False

    # Last known good price
    if _price_cache["value"] is not None:
        is_stale = (now - _price_cache["fetched_at"]).total_seconds() > STALE_THRESHOLD_SECONDS
        logger.warning("Using cached price %.2f (stale=%s)", _price_cache["value"], is_stale)
        return _price_cache["value"], _price_cache["fetched_at"], is_stale

    # Hard fallback
    logger.error("All price oracles failed, using hard fallback %.2f", HARD_FALLBACK_PRICE)
    return HARD_FALLBACK_PRICE, now, True


@router.get("/pricing")
def get_pricing():
    """Return current SUI prices for all subscription tiers."""
    sui_usd, fetched_at, is_stale = get_sui_price()

    tiers = {}
    for key, tier in TIERS.items():
        sui_amount = round(tier["usd_per_week"] / sui_usd, 2)
        tiers[key] = {
            "usd_per_week": tier["usd_per_week"],
            "sui_per_week": sui_amount,
            "sui_mist": int(sui_amount * 1_000_000_000),
            "tier": tier["tier"],
        }

    return {
        "sui_usd": round(sui_usd, 4),
        "fetched_at": fetched_at.isoformat(),
        "is_stale": is_stale,
        "tiers": tiers,
    }
