"""Phase 4 — S3 (or any S3-compatible store: Cloudflare R2, MinIO, ...)
client wrapper.

The one rule this whole module exists to enforce: FastAPI never touches the
file's bytes. The client uploads directly to the bucket using a pre-signed
URL we hand it, and downloads directly from the CDN in front of that bucket.
Our process only ever generates URLs and writes a database row -- see the
Phase 4 "never proxy file bytes through FastAPI" gotcha in the build plan.
"""
import uuid

import boto3
from botocore.client import Config as BotoConfig

from .config import settings

_ALLOWED_CONTENT_TYPES = {
    ct.strip() for ct in settings.media_allowed_content_types.split(",") if ct.strip()
}


def _s3_client():
    """A fresh boto3 client per call is cheap (boto3 pools connections
    internally) and keeps this module free of global mutable state, which
    matters once you're running under multiple uvicorn workers."""
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id or None,
        aws_secret_access_key=settings.s3_secret_access_key or None,
        # Only set for R2/MinIO/local dev. Leave settings.s3_endpoint_url=""
        # and boto3 talks to real AWS S3 using s3_region instead.
        endpoint_url=settings.s3_endpoint_url or None,
        config=BotoConfig(signature_version="s3v4"),
    )


class UnsupportedMediaType(ValueError):
    pass


def validate_upload_request(content_type: str) -> None:
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise UnsupportedMediaType(
            f"Content-type '{content_type}' is not allowed. Allowed: {sorted(_ALLOWED_CONTENT_TYPES)}"
        )


def build_object_key(user_id: int, filename: str) -> str:
    """uploads/<user_id>/<random>-<original filename>. The random prefix
    stops two users' "photo.jpg" from colliding, and namespacing by user_id
    makes it trivial to find/delete everything one user has ever uploaded."""
    safe_name = filename.replace("/", "_").replace("\\", "_")
    return f"uploads/{user_id}/{uuid.uuid4().hex[:12]}-{safe_name}"


def generate_presigned_upload_url(object_key: str, content_type: str) -> str:
    """A pre-signed URL is a normal S3 URL with a cryptographic signature
    baked into the query string, proving *we* (who hold the AWS secret key)
    authorized this specific PUT, to this specific key, within a time limit
    -- without ever handing that secret key to the browser."""
    client = _s3_client()
    return client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.media_upload_url_expire_seconds,
    )


def cdn_url_for(object_key: str) -> str:
    """Public, cacheable URL a browser downloads the file from -- routed
    through the CDN in front of the bucket, never the raw bucket endpoint
    (which likely isn't even publicly readable, and wouldn't be geo-cached
    or edge-cached if it were)."""
    return f"{settings.cdn_base_url.rstrip('/')}/{object_key}"
