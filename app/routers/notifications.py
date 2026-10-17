"""Phase 5 — read side of notifications. The write side lives in tasks.py
and is triggered from comments.py / follows.py, not from here."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, oauth2, schemas
from ..database import get_db

router = APIRouter(tags=["Notifications"], responses={404: {"description": "Not found"}})


@router.get("/notifications", response_model=list[schemas.NotificationResponse], status_code=status.HTTP_200_OK)
def get_notifications(
    is_read: bool | None = Query(None, description="Filter to only read (true) or only unread (false) notifications"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    query = (
        db.query(models.Notifications)
        .options(joinedload(models.Notifications.actor))
        .filter(models.Notifications.recipient_id == current_user.id)
    )
    if is_read is not None:
        query = query.filter(models.Notifications.is_read == is_read)

    return (
        query.order_by(models.Notifications.created_at.desc())
        .limit(limit)
        .offset(skip)
        .all()
    )


@router.get("/notifications/unread-count", response_model=schemas.UnreadCountResponse, status_code=status.HTTP_200_OK)
def get_unread_count(db: Session = Depends(get_db), current_user=Depends(oauth2.get_current_user)):
    # Cheap enough to compute at read-time (an indexed count) that this
    # doesn't need a cache the way the feed does. If polling this
    # endpoint every few seconds from many clients ever becomes hot enough
    # to matter, it's a good candidate for the same Redis-cache pattern
    # feed.py already establishes.
    count = (
        db.query(models.Notifications)
        .filter(models.Notifications.recipient_id == current_user.id, models.Notifications.is_read.is_(False))
        .count()
    )
    return schemas.UnreadCountResponse(unread_count=count)


@router.patch("/notifications/{id}/read", response_model=schemas.NotificationResponse, status_code=status.HTTP_200_OK)
def mark_notification_read(id: int, db: Session = Depends(get_db), current_user=Depends(oauth2.get_current_user)):
    notification_query = db.query(models.Notifications).filter(models.Notifications.id == id)
    notification = notification_query.first()

    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Notification with id {id} not found")

    if notification.recipient_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This notification does not belong to you")

    notification_query.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return notification_query.first()
