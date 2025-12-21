from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI

from ..core.logging import setup_logging
from .api.v1.router import router as api_router
from .config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging()
    settings = get_settings()
    if settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
    yield
    # Shutdown


app = FastAPI(
    title="AI Code Reviewer",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
