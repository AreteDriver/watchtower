"""Stripe webhook + checkout handler — USD payment path for WatchTower subscriptions.

Receives checkout.session.completed events from Stripe.
Maps payment to tier via metadata, records subscription in DB.
Provides /checkout/create to initiate Stripe Checkout sessions.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.analysis.subscriptions import record_subscription
from backend.api.pricing import get_sui_price
from backend.core.config import settings
from backend.core.logger import get_logger
from backend.db.database import get_db

logger = get_logger("stripe")

router = APIRouter()

# Tier mapping from Stripe product metadata
STRIPE_TIER_MAP = {
    "scout": 1,
    "oracle": 2,
    "spymaster": 3,
}

# Price in cents per tier
STRIPE_TIER_PRICES = {
    1: 499,  # Scout $4.99
    2: 999,  # Oracle $9.99
    3: 1999,  # Spymaster $19.99
}

STRIPE_TIER_NAMES = {1: "Scout", 2: "Oracle", 3: "Spymaster"}

# Frontend URL for redirect after checkout
FRONTEND_URL = "https://watchtower-evefrontier.vercel.app"


class CheckoutRequest(BaseModel):
    tier: int


@router.post("/checkout/create")
async def create_checkout(body: CheckoutRequest, request: Request) -> dict:
    """Create a Stripe Checkout Session for the given tier.

    Requires wallet auth via X-Wallet-Address header.
    Returns {"url": "https://checkout.stripe.com/..."} for redirect.
    """
    try:
        import stripe
    except ImportError as err:
        raise HTTPException(500, "Stripe SDK not installed") from err

    wallet = request.headers.get("X-Wallet-Address", "")
    if not wallet:
        raise HTTPException(401, "Wallet not connected")

    if body.tier not in STRIPE_TIER_PRICES:
        raise HTTPException(400, f"Invalid tier: {body.tier}")

    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(500, "Stripe not configured")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    tier_name = STRIPE_TIER_NAMES[body.tier]
    price_cents = STRIPE_TIER_PRICES[body.tier]

    # Lock SUI equivalent at checkout time
    sui_usd, _fetched_at, _is_stale = get_sui_price()
    sui_amount = round(price_cents / 100 / sui_usd, 4)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"WatchTower {tier_name} Subscription"},
                        "unit_amount": price_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "wallet_address": wallet,
                "tier": tier_name.lower(),
                "sui_amount": str(sui_amount),
                "sui_usd_at_checkout": str(round(sui_usd, 4)),
            },
            success_url=f"{FRONTEND_URL}/account?checkout=success",
            cancel_url=f"{FRONTEND_URL}/account?checkout=cancelled",
        )
    except Exception as e:
        logger.error("Stripe checkout session creation failed: %s", e)
        raise HTTPException(502, "Failed to create checkout session") from e

    logger.info("Stripe checkout created: wallet=%s tier=%s", wallet[:16], tier_name)
    return {"url": session.url}


# Duration per purchase (7 days default, 30 for monthly)
DURATION_MAP = {
    "weekly": 7 * 86400,
    "monthly": 30 * 86400,
}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Handle Stripe webhook events.

    Validates signature, dispatches to handler by event type.
    """
    try:
        import stripe
    except ImportError as err:
        raise HTTPException(500, "Stripe SDK not installed") from err

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(500, "Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError as err:
        logger.warning("Stripe webhook: invalid signature")
        raise HTTPException(400, "Invalid signature") from err
    except Exception as e:
        logger.error("Stripe webhook verification failed: %s", e)
        raise HTTPException(400, "Verification failed") from e

    event_type = event.get("type", "")
    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        return _handle_checkout(event)

    # Acknowledge unhandled events
    return {"received": True, "event_type": event_type, "handled": False}


def _handle_checkout(event: dict) -> dict:
    """Process a completed checkout session.

    Expected metadata on the Stripe checkout/payment link:
      - wallet_address: Sui wallet to credit
      - tier: scout|oracle|spymaster
      - duration: weekly|monthly (default: weekly)
    """
    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata", {})

    wallet = metadata.get("wallet_address", "")
    tier_name = metadata.get("tier", "").lower()
    duration_key = metadata.get("duration", "weekly").lower()

    if not wallet:
        logger.error(
            "Stripe checkout missing wallet_address in metadata: %s",
            session.get("id", ""),
        )
        return {"received": True, "handled": False, "error": "missing wallet_address"}

    tier = STRIPE_TIER_MAP.get(tier_name)
    if tier is None:
        logger.error("Stripe checkout invalid tier '%s': %s", tier_name, session.get("id", ""))
        return {"received": True, "handled": False, "error": f"invalid tier: {tier_name}"}

    duration = DURATION_MAP.get(duration_key, 7 * 86400)

    db = get_db()
    result = record_subscription(db, wallet, tier, duration)

    logger.info(
        "Stripe subscription recorded: wallet=%s tier=%d duration=%s stripe_session=%s",
        wallet[:16],
        tier,
        duration_key,
        session.get("id", "")[:24],
    )

    # Store Stripe reference for potential refunds/cancellations
    stripe_customer = session.get("customer", "")
    stripe_sub = session.get("subscription", "")
    if stripe_customer or stripe_sub:
        try:
            db.execute(
                """UPDATE watcher_subscriptions
                   SET stripe_customer_id = ?, stripe_subscription_id = ?
                   WHERE wallet_address = ?""",
                (stripe_customer, stripe_sub, wallet),
            )
            db.commit()
        except Exception:
            pass  # Columns may not exist yet, best-effort

    return {
        "received": True,
        "handled": True,
        "wallet": wallet[:16],
        "tier": tier,
        "tier_name": tier_name,
        "expires_at": result.get("expires_at", 0),
    }
