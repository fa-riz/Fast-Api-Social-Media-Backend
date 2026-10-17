"""Phase 4 — Media uploads.

Two-step flow, both required:
  1. POST /media/upload-url  -> client gets a pre-signed URL, uploads the
     file bytes DIRECTLY to S3/R2 (not through this API).
  2. POST /media             -> client tells us the upload finished, we
     persist a Media row.

Step 2 exists because step 1 alone can't tell us whether the upload actually
succeeded -- the client might get the pre-signed URL and then never use it,
or the upload might fail partway through.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, oauth2, schemas, storage
from ..config import settings
from ..database import get_db

router = APIRouter(tags=["Media"], responses={404: {"description": "Not found"}})


@router.post("/media/upload-url", response_model=schemas.MediaUploadResponse, status_code=status.HTTP_200_OK)
def create_upload_url(
    payload: schemas.MediaUploadRequest,
    current_user=Depends(oauth2.get_current_user),
):
    # Validate BEFORE generating a signed URL -- there's no point signing a
    # URL for an upload we're going to reject at confirm time anyway, and
    # this is the one place we can cheaply reject an obviously-wrong
    # content-type before any bytes move.
    try:
        storage.validate_upload_request(payload.content_type)
    except storage.UnsupportedMediaType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))

    if payload.media_type not in ("image", "video"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="media_type must be 'image' or 'video'")

    object_key = storage.build_object_key(current_user.id, payload.filename)
    upload_url = storage.generate_presigned_upload_url(object_key, payload.content_type)

    return schemas.MediaUploadResponse(
        upload_url=upload_url,
        object_key=object_key,
        cdn_url=storage.cdn_url_for(object_key),
        expires_in=settings.media_upload_url_expire_seconds,
    )


@router.post("/media", response_model=schemas.MediaResponse, status_code=status.HTTP_201_CREATED)
def confirm_upload(
    payload: schemas.MediaConfirm,
    db: Session = Depends(get_db),
    current_user=Depends(oauth2.get_current_user),
):
    # Namespacing object keys under uploads/{user_id}/... (see storage.py)
    # doubles as a cheap ownership check here: a user can't confirm a key
    # they weren't issued.
    if not payload.object_key.startswith(f"uploads/{current_user.id}/"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This upload was not issued to you")

    if payload.post_id is not None:
        post = db.query(models.Posts).filter(models.Posts.id == payload.post_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Post with id {payload.post_id} not found")
        if post.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only attach media to your own posts")

    existing = db.query(models.Media).filter(models.Media.object_key == payload.object_key).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This upload has already been confirmed")

    new_media = models.Media(
        url=storage.cdn_url_for(payload.object_key),
        media_type=payload.media_type,
        object_key=payload.object_key,
        post_id=payload.post_id,
        user_id=current_user.id,
    )
    db.add(new_media)
    db.commit()
    db.refresh(new_media)
    return new_media
