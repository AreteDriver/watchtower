"""Tests for the SUI fiat-pegged pricing oracle."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.pricing import (
    HARD_FALLBACK_PRICE,
    TIERS,
    _price_cache,
    get_sui_price,
    router,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    """Reset price cache between tests."""
    _price_cache["value"] = None
    _price_cache["fetched_at"] = None
    yield
    _price_cache["value"] = None
    _price_cache["fetched_at"] = None


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app)


class TestGetSuiPrice:
    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_coingecko_primary(self, mock_cg, mock_bn):
        price, fetched_at, is_stale = get_sui_price()
        assert price == 3.42
        assert not is_stale
        mock_cg.assert_called_once()
        mock_bn.assert_not_called()

    @patch("backend.api.pricing._fetch_binance", return_value=3.50)
    @patch("backend.api.pricing._fetch_coingecko", return_value=None)
    def test_binance_fallback(self, mock_cg, mock_bn):
        price, _, is_stale = get_sui_price()
        assert price == 3.50
        assert not is_stale
        mock_cg.assert_called_once()
        mock_bn.assert_called_once()

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=None)
    def test_hard_fallback(self, mock_cg, mock_bn):
        price, _, is_stale = get_sui_price()
        assert price == HARD_FALLBACK_PRICE
        assert is_stale

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=None)
    def test_cached_price_used_when_oracles_fail(self, mock_cg, mock_bn):
        _price_cache["value"] = 4.00
        _price_cache["fetched_at"] = datetime.now(tz=UTC) - timedelta(seconds=30)
        price, _, is_stale = get_sui_price()
        assert price == 4.00
        assert not is_stale

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=None)
    def test_stale_cached_price(self, mock_cg, mock_bn):
        _price_cache["value"] = 4.00
        _price_cache["fetched_at"] = datetime.now(tz=UTC) - timedelta(seconds=400)
        price, _, is_stale = get_sui_price()
        assert price == 4.00
        assert is_stale

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_cache_hit_skips_fetch(self, mock_cg, mock_bn):
        _price_cache["value"] = 3.00
        _price_cache["fetched_at"] = datetime.now(tz=UTC) - timedelta(seconds=10)
        price, _, _ = get_sui_price()
        assert price == 3.00
        mock_cg.assert_not_called()
        mock_bn.assert_not_called()

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_cache_expired_refetches(self, mock_cg, mock_bn):
        _price_cache["value"] = 3.00
        _price_cache["fetched_at"] = datetime.now(tz=UTC) - timedelta(seconds=120)
        price, _, _ = get_sui_price()
        assert price == 3.42
        mock_cg.assert_called_once()


class TestPricingEndpoint:
    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_pricing_response_structure(self, mock_cg, mock_bn, client):
        r = client.get("/api/pricing")
        assert r.status_code == 200
        data = r.json()
        assert "sui_usd" in data
        assert "fetched_at" in data
        assert "is_stale" in data
        assert "tiers" in data
        assert set(data["tiers"].keys()) == {"scout", "oracle", "spymaster"}

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_tier_calculation(self, mock_cg, mock_bn, client):
        r = client.get("/api/pricing")
        data = r.json()
        scout = data["tiers"]["scout"]
        assert scout["usd_per_week"] == 4.99
        assert scout["sui_per_week"] == round(4.99 / 3.42, 2)
        assert scout["sui_mist"] == int(scout["sui_per_week"] * 1_000_000_000)
        assert scout["tier"] == 1

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=3.42)
    def test_all_tiers_present(self, mock_cg, mock_bn, client):
        r = client.get("/api/pricing")
        data = r.json()
        for key, tier in TIERS.items():
            assert data["tiers"][key]["usd_per_week"] == tier["usd_per_week"]
            assert data["tiers"][key]["tier"] == tier["tier"]

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=None)
    def test_stale_flag_on_fallback(self, mock_cg, mock_bn, client):
        r = client.get("/api/pricing")
        data = r.json()
        assert data["is_stale"] is True
        assert data["sui_usd"] == HARD_FALLBACK_PRICE

    @patch("backend.api.pricing._fetch_binance", return_value=None)
    @patch("backend.api.pricing._fetch_coingecko", return_value=2.00)
    def test_two_decimal_precision(self, mock_cg, mock_bn, client):
        r = client.get("/api/pricing")
        data = r.json()
        for tier in data["tiers"].values():
            sui_str = str(tier["sui_per_week"])
            decimals = sui_str.split(".")[-1] if "." in sui_str else ""
            assert len(decimals) <= 2
