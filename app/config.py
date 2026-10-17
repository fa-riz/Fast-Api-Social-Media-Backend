from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Phase 3: Feed / Redis cache ---------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    feed_cache_ttl_seconds: int = 90        # how long a cached feed page is served before recompute
    feed_score_decay_hours: float = 12.0    # "hot" score half-life-ish constant, see feed.py

    # --- Phase 4: Media uploads (S3 / R2 + CDN) ----------------------------
    s3_bucket: str = "change-me-bucket"
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    # Leave blank for real AWS S3. Set to a URL (e.g. Cloudflare R2's account
    # endpoint, or http://localhost:9000 for local MinIO) for anything
    # S3-compatible that isn't AWS itself.
    s3_endpoint_url: str = ""
    # Public CDN domain the browser actually downloads media from. Never the
    # raw bucket URL -- see the Phase 4 "never proxy file bytes" gotcha.
    cdn_base_url: str = "https://cdn.example.com"
    media_upload_url_expire_seconds: int = 300
    media_max_size_bytes: int = 25 * 1024 * 1024  # 25 MB
    media_allowed_content_types: str = "image/jpeg,image/png,image/webp,image/gif,video/mp4"

    # --- Phase 5: Notifications job queue (Celery) -------------------------
    # Same Redis instance as the feed cache, different logical DB number --
    # one Redis, multiple uses (see build-plan "cross-phase" note).
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Phase 6: Direct messaging (WebSocket) ------------------------------
    # No extra settings needed yet -- messaging reuses the same JWT auth as
    # everything else. Kept as a section marker for symmetry with the docx.

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
