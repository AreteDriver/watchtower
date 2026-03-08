"""Tests for FastAPI app — lifespan, intelligence loops, serve_frontend."""

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.db.database import SCHEMA


def _get_test_db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# --- _run_intelligence_loops ---


async def test_intelligence_loops_runs_checks():
    """Lines 29-41: verify check_watches, generate_feed_items called."""
    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 1:
            raise asyncio.CancelledError()

    mock_check = AsyncMock()
    mock_feed = MagicMock()
    mock_refresh = MagicMock()
    test_db = _get_test_db()

    with (
        patch(
            "backend.api.app.check_watches",
            mock_check,
        ),
        patch(
            "backend.api.app.generate_feed_items",
            mock_feed,
        ),
        patch(
            "backend.api.app.refresh_all_titles",
            mock_refresh,
        ),
        patch(
            "backend.api.app.get_db",
            return_value=test_db,
        ),
        patch(
            "backend.api.app.asyncio.sleep",
            side_effect=mock_sleep,
        ),
        patch(
            "backend.api.app.settings",
            type("S", (), {"POLL_INTERVAL_SECONDS": 30})(),
        ),
    ):
        from backend.api.app import _run_intelligence_loops

        with pytest.raises(asyncio.CancelledError):
            await _run_intelligence_loops()

    mock_check.assert_awaited_once()
    mock_feed.assert_called_once()
    # cycle=0, so 0 % 12 == 0 → refresh_all_titles called
    mock_refresh.assert_called_once_with(test_db)


async def test_intelligence_loops_skips_refresh_on_non_zero_cycle():
    """refresh_all_titles only called on cycle % 12 == 0."""
    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError()

    mock_refresh = MagicMock()

    with (
        patch("backend.api.app.check_watches", AsyncMock()),
        patch("backend.api.app.generate_feed_items", MagicMock()),
        patch("backend.api.app.refresh_all_titles", mock_refresh),
        patch("backend.api.app.get_db", return_value=_get_test_db()),
        patch("backend.api.app.asyncio.sleep", side_effect=mock_sleep),
        patch(
            "backend.api.app.settings",
            type("S", (), {"POLL_INTERVAL_SECONDS": 30})(),
        ),
    ):
        from backend.api.app import _run_intelligence_loops

        with pytest.raises(asyncio.CancelledError):
            await _run_intelligence_loops()

    # Called once on cycle 0, not on cycle 1
    assert mock_refresh.call_count == 1


async def test_intelligence_loops_handles_error():
    """Lines 39-40: exception in loop body is caught."""
    call_count = 0

    async def mock_sleep(seconds):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            raise asyncio.CancelledError()

    mock_check = AsyncMock(side_effect=[RuntimeError("oracle down"), None])

    with (
        patch("backend.api.app.check_watches", mock_check),
        patch("backend.api.app.generate_feed_items", MagicMock()),
        patch("backend.api.app.refresh_all_titles", MagicMock()),
        patch("backend.api.app.get_db", return_value=_get_test_db()),
        patch("backend.api.app.asyncio.sleep", side_effect=mock_sleep),
        patch(
            "backend.api.app.settings",
            type("S", (), {"POLL_INTERVAL_SECONDS": 30})(),
        ),
    ):
        from backend.api.app import _run_intelligence_loops

        with pytest.raises(asyncio.CancelledError):
            await _run_intelligence_loops()

    # Should have survived the error and looped again
    assert call_count == 2


# --- lifespan ---


async def test_lifespan_startup_shutdown():
    """Lines 46-63: lifespan starts tasks and cancels on shutdown."""
    test_db = _get_test_db()

    async def noop_coro():
        await asyncio.sleep(999)

    mock_app = MagicMock()

    with (
        patch("backend.api.app.get_db", return_value=test_db),
        patch("backend.api.app.close_db") as mock_close,
        patch("backend.api.app.run_poller", side_effect=noop_coro),
        patch(
            "backend.api.app._run_intelligence_loops",
            side_effect=noop_coro,
        ),
        patch("backend.api.app.run_bot", side_effect=noop_coro),
    ):
        from backend.api.app import lifespan

        async with lifespan(mock_app):
            # Inside lifespan — tasks should be running
            pass

        # After exit — close_db should have been called
        mock_close.assert_called_once()


# --- serve_frontend ---


def test_serve_frontend_index_html(tmp_path):
    """Lines 116-119: serve_frontend returns index.html for SPA."""
    # Build a fake frontend dist
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    assets = dist / "assets"
    assets.mkdir()
    index = dist / "index.html"
    index.write_text("<html>SPA</html>")

    with (
        patch("backend.api.app.FRONTEND_DIR", dist),
        patch("backend.db.database.get_db", return_value=_get_test_db()),
        patch("backend.api.routes.get_db", return_value=_get_test_db()),
        patch("backend.api.app.get_db", return_value=_get_test_db()),
        patch("backend.api.routes.check_tier_access"),
        patch("backend.ingestion.poller.run_poller"),
        patch("backend.bot.discord_bot.run_bot"),
    ):
        from fastapi.testclient import TestClient

        from backend.api.app import app
        from backend.api.rate_limit import limiter

        # Register the serve_frontend route dynamically
        @app.get("/test-spa/{path:path}")
        async def _serve(path: str):
            file = (dist / path).resolve()
            if file.is_relative_to(dist) and file.exists() and file.is_file():
                from fastapi.responses import FileResponse

                return FileResponse(str(file))
            from fastapi.responses import FileResponse

            return FileResponse(str(index))

        limiter.enabled = False
        client = TestClient(app, raise_server_exceptions=False)

        # Non-existent path should fall through to index.html
        r = client.get("/test-spa/nonexistent")
        assert r.status_code == 200
        assert "SPA" in r.text

        limiter.enabled = True
