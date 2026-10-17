from fastapi import FastAPI

from . import models  # noqa: F401 (import registers all tables on Base.metadata for Alembic)
from .routers import posts, users, auth, votes, comments, follows, feed, media, notifications, messages

# Phase 0 introduces Alembic. Schema is now managed by migrations
# (`alembic upgrade head`), not by create_all() on every app start -- see
# /alembic/versions and the README in the docx for the one-time setup steps.

app = FastAPI()

app.include_router(posts.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(votes.router)
app.include_router(comments.router)       # Phase 1: comments + threaded replies
app.include_router(follows.router)        # Phase 2: follow / follower graph
app.include_router(feed.router)           # Phase 3: feed generation (Redis-cached ranking)
app.include_router(media.router)          # Phase 4: media uploads (S3/R2 + CDN)
app.include_router(notifications.router)  # Phase 5: notifications (Celery + Redis job queue)
app.include_router(messages.router)       # Phase 6: direct messaging (REST + WebSocket)


@app.get("/")
async def root():
    return {"message": "Hello World !!"}
