"""Phase 5 — background jobs, run by the Celery worker process, not by the
FastAPI request/response cycle.

Golden rule (see build-plan gotcha): never write a notification
synchronously in the request path. `create_comment`, `follow_user`, `vote`,
`create_post` and `send_message` call `.delay(...)` on the tasks below, which just
serializes the arguments onto the Redis broker and returns immediately --
the actual DB write happens later, in the worker process, off the critical
path of the user's request.
"""
import logging

from .celery_app import celery_app
from .database import SessionLocal
from . import models

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.create_notification_task",
    autoretry_for=(Exception,),
    retry_backoff=True,       # 1s, 2s, 4s, ... between attempts, not a hot retry loop
    retry_kwargs={"max_retries": 3},
)
def create_notification_task(recipient_id: int, actor_id: int, type_: str, target_type: str, target_id: int) -> None:
    """Runs in the worker process, so it opens its own DB session --
    it cannot reuse the request-scoped `db` from `database.get_db()`,
    which is closed long before this task actually executes."""
    if recipient_id == actor_id:
        # Never notify someone about their own action (e.g. commenting on
        # your own post, or -- impossible today, but defensive -- following
        # yourself).
        return

    db = SessionLocal()
    try:
        notification = models.Notifications(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type=type_,
            target_type=target_type,
            target_id=target_id,
        )
        db.add(notification)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to create notification (recipient=%s, actor=%s, type=%s)",
            recipient_id, actor_id, type_,
        )
        raise  # let autoretry_for above decide whether to try again
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.notify_followers_of_post_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def notify_followers_of_post_task(author_id: int, post_id: int) -> None:
    """Fan-out for a new post: one notification per follower of the author.
    Done here in a single task (one query + one bulk insert) rather than the
    request enqueueing one create_notification_task per follower, which
    would put O(followers) work back on the request path."""
    db = SessionLocal()
    try:
        follower_ids = [
            row[0]
            for row in db.query(models.Follows.follower_id)
            .filter(models.Follows.followed_id == author_id)
            .all()
        ]
        if not follower_ids:
            return
        db.add_all([
            models.Notifications(
                recipient_id=follower_id,
                actor_id=author_id,
                type="post",
                target_type="post",
                target_id=post_id,
            )
            for follower_id in follower_ids
        ])
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to fan out post notifications (author=%s, post=%s)", author_id, post_id)
        raise
    finally:
        db.close()
