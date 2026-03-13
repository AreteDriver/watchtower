"""Tests for Stripe webhook handler."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.db.database import SCHEMA


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@pytest.fixture
def client(db):
    """TestClient with Stripe webhook secret configured and DB patched."""
    with (
        patch("backend.api.stripe_webhook.settings") as mock_settings,
        patch("backend.api.stripe_webhook.get_db", return_value=db),
    ):
        mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test_secret"

        from backend.api.stripe_webhook import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app)


def _make_event(wallet="0xTestWallet", tier="oracle", duration="weekly"):
    """Build a mock Stripe checkout.session.completed event."""
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc123",
                "metadata": {
                    "wallet_address": wallet,
                    "tier": tier,
                    "duration": duration,
                },
                "customer": "cus_test_123",
                "subscription": "sub_test_456",
            }
        },
    }


class TestStripeWebhook:
    def test_missing_stripe_sdk(self, db):
        """Should 500 if stripe package not importable."""
        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            # Patch the import inside the function to fail
            import builtins

            real_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "stripe":
                    raise ImportError("no stripe")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                resp = client.post(
                    "/webhooks/stripe",
                    content=b"{}",
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
                assert resp.status_code == 500

    def test_missing_webhook_secret(self, db):
        """Should 500 if STRIPE_WEBHOOK_SECRET not configured."""
        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = ""

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert resp.status_code == 500

    @patch("stripe.Webhook.construct_event")
    def test_checkout_completed_records_subscription(self, mock_construct, db):
        """Valid checkout should record subscription in DB."""
        event = _make_event()
        mock_construct.return_value = event

        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["handled"] is True
            assert data["tier"] == 2
            assert data["tier_name"] == "oracle"

    @patch("stripe.Webhook.construct_event")
    def test_checkout_missing_wallet(self, mock_construct, db):
        """Checkout without wallet_address in metadata should not record."""
        event = _make_event(wallet="")
        mock_construct.return_value = event

        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["handled"] is False
            assert "missing wallet_address" in data["error"]

    @patch("stripe.Webhook.construct_event")
    def test_checkout_invalid_tier(self, mock_construct, db):
        """Checkout with invalid tier should not record."""
        event = _make_event(tier="emperor")
        mock_construct.return_value = event

        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["handled"] is False
            assert "invalid tier" in data["error"]

    @patch("stripe.Webhook.construct_event")
    def test_unhandled_event_type(self, mock_construct, db):
        """Non-checkout events should be acknowledged but not handled."""
        mock_construct.return_value = {"type": "payment_intent.succeeded"}

        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["handled"] is False

    @patch("stripe.Webhook.construct_event")
    def test_all_tiers_accepted(self, mock_construct, db):
        """Scout, Oracle, Spymaster all produce correct tier numbers."""
        for tier_name, expected_tier in [
            ("scout", 1),
            ("oracle", 2),
            ("spymaster", 3),
        ]:
            event = _make_event(
                wallet=f"0xWallet_{tier_name}", tier=tier_name
            )
            mock_construct.return_value = event

            with (
                patch("backend.api.stripe_webhook.settings") as mock_settings,
                patch("backend.api.stripe_webhook.get_db", return_value=db),
            ):
                mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

                from backend.api.stripe_webhook import router
                from fastapi import FastAPI

                app = FastAPI()
                app.include_router(router)
                client = TestClient(app)

                resp = client.post(
                    "/webhooks/stripe",
                    content=b"{}",
                    headers={"stripe-signature": "t=1,v1=abc"},
                )
                data = resp.json()
                assert data["tier"] == expected_tier

    @patch("stripe.Webhook.construct_event")
    def test_monthly_duration(self, mock_construct, db):
        """Monthly duration should extend expiry to ~30 days."""
        import time

        event = _make_event(duration="monthly")
        mock_construct.return_value = event

        with (
            patch("backend.api.stripe_webhook.settings") as mock_settings,
            patch("backend.api.stripe_webhook.get_db", return_value=db),
        ):
            mock_settings.STRIPE_WEBHOOK_SECRET = "whsec_test"

            from backend.api.stripe_webhook import router
            from fastapi import FastAPI

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app)

            resp = client.post(
                "/webhooks/stripe",
                content=b"{}",
                headers={"stripe-signature": "t=1,v1=abc"},
            )
            data = resp.json()
            assert data["handled"] is True
            # Expiry should be ~30 days out
            assert data["expires_at"] > time.time() + 29 * 86400
