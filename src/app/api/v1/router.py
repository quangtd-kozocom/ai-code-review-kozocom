from fastapi import APIRouter

from .health import router as health_router
from .webhooks import router as webhooks_router
from .reviews import router as reviews_router
from .repositories import router as repositories_router

router = APIRouter()

router.include_router(webhooks_router)
router.include_router(health_router)
router.include_router(reviews_router)
router.include_router(repositories_router)
