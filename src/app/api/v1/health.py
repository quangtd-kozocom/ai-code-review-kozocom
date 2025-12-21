from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "ai-code-reviewer",
    }
