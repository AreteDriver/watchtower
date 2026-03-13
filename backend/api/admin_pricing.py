"""Admin price sync — generates CLI command to update on-chain prices."""

from fastapi import APIRouter, HTTPException, Request

from backend.api.pricing import TIERS, get_sui_price
from backend.api.tier_gate import is_admin_wallet
from backend.core.logger import get_logger

logger = get_logger("admin_pricing")

router = APIRouter()

PACKAGE = "0x3ca7e3af5bf5b072157d02534f5e4013cf11a12b79385c270d97de480e7b7dca"
CONFIG = "0x7bd0e266d3c26665b13c432f70d9b7e5ecc266de993094f8ac8290020283be9d"
ADMIN_CAP = "0x5af68eea339255f184218108fa52859a08b572e2f906940bafbed436cbbeaaae"


def sui_to_mist(sui_amount: float) -> int:
    """Convert SUI amount to MIST (1 SUI = 1_000_000_000 MIST)."""
    return int(round(sui_amount * 1_000_000_000))


@router.post("/admin/sync-prices")
async def sync_prices(request: Request):
    """Calculate current MIST prices and generate CLI command."""
    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet or not is_admin_wallet(wallet):
        raise HTTPException(status_code=403, detail="Admin access required.")

    sui_usd, fetched_at, is_stale = get_sui_price()

    prices = {}
    for key, tier in TIERS.items():
        sui_amount = round(tier["usd_per_week"] / sui_usd, 2)
        mist = sui_to_mist(sui_amount)
        prices[key] = {
            "usd": tier["usd_per_week"],
            "sui": sui_amount,
            "mist": mist,
        }

    # Generate CLI command for manual execution
    cli_cmd = (
        f"sui client call "
        f"--package {PACKAGE} "
        f"--module subscription "
        f"--function update_prices "
        f"--args {ADMIN_CAP} {CONFIG} "
        f"{prices['scout']['mist']} "
        f"{prices['oracle']['mist']} "
        f"{prices['spymaster']['mist']} "
        f"--gas-budget 10000000"
    )

    logger.info(
        "Price sync requested by %s — SUI/USD=%.4f, scout=%d, oracle=%d, spymaster=%d MIST",
        wallet,
        sui_usd,
        prices["scout"]["mist"],
        prices["oracle"]["mist"],
        prices["spymaster"]["mist"],
    )

    return {
        "sui_usd": round(sui_usd, 4),
        "fetched_at": fetched_at.isoformat(),
        "is_stale": is_stale,
        "prices": prices,
        "cli_command": cli_cmd,
    }
