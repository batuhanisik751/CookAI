from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "cookai",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=600,
    task_time_limit=660,
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-media": {
        "task": "app.workers.tasks.cleanup_expired_media_task",
        "schedule": 3600.0,
    },
}

celery_app.autodiscover_tasks(["app.workers"])
