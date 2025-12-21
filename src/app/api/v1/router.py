from fastapi import APIRouter

from .health import router as health_router
from .webhooks import router as webhooks_router

router = APIRouter()

router.include_router(webhooks_router)
router.include_router(health_router)
