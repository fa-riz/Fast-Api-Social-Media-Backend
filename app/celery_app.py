"""Phase 5 — Celery application instance.

This is the object a worker process loads to know what tasks exist and
where to get work from:

    celery -A app.celery_app worker --loglevel=info

It's deliberately a separate module from tasks.py: `celery_app` is imported
by both the FastAPI process (to *enqueue* tasks) and the worker process (to
*run* them), while tasks.py additionally needs FastAPI's db/models imports
that the FastAPI process already paid the cost of loading.
"""
from celery import Celery

from .config import settings

celery_app = Celery(
    "app",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # A notification task should retry a couple of times on transient
    # failure (DB hiccup, Redis blip) but never hang forever -- see the
    # Phase 5 gotcha: "this is the first phase where a slow background job
    # could silently fail; add logging/retry from day one".
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# So `celery -A app.celery_app worker` discovers the @celery_app.task
# functions in tasks.py without a separate --include flag.
celery_app.autodiscover_tasks(["app"], related_name="tasks")
