from celery import Celery

from ..app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_reviewer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    task_track_started=True,
    task_time_limit=300,  # 5 min max
    task_soft_time_limit=280,  # Soft limit 4:40
    worker_prefetch_multiplier=1,  # One task at a time per worker
    task_acks_late=True,  # Ack after completion
)
