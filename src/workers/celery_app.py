import ssl

from celery import Celery

from ..app.config import get_settings
from ..core.constants import CELERY_TASK_SOFT_TIME_LIMIT, CELERY_TASK_TIME_LIMIT

settings = get_settings()

redis_ssl_options = None
if settings.REDIS_URL.startswith("rediss://"):
    redis_ssl_options = {
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_ca_certs": None,
    }

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
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

if redis_ssl_options:
    celery_app.conf.update(
        broker_use_ssl=redis_ssl_options,
        redis_backend_use_ssl=redis_ssl_options,
    )
