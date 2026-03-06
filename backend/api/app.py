"""FastAPI application — Witness API server."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.core.logger import get_logger
from backend.db.database import close_db, get_db
from backend.ingestion.poller import run_poller

logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Witness starting up")
    get_db()

    # Start poller as background task
    poller_task = asyncio.create_task(run_poller())

    yield

    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    close_db()
    logger.info("Witness shut down")


app = FastAPI(
    title="Witness",
    description="The Living Memory of EVE Frontier",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
