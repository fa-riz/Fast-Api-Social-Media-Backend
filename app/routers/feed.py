"""Phase 3 — Feed generation.

Two modes behind one endpoint:
  - `sort=recent` (default): plain reverse-chronological feed of posts from
    people you follow. Cursor-paginated, no Redis involved.
  - `sort=hot`: ranked by a Reddit-style score (votes vs. age). This is the
    first place Redis shows up in the build -- see `_hot_feed` below.

See the docx's Phase 3 section for the full walkthrough of *why* each piece
here looks the way it does; this file sticks to a plan-order build order
comment trail instead of re-explaining the theory inline.
"""
import math
from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, tuple_
from sqlalchemy.orm import Session

from .. import models, oauth2, schemas
from ..config import settings
from ..database import get_db
from ..pagination import decode_cursor, encode_cursor
from ..redis_client import get_redis

router = APIRouter(tags=["Feed"])


def _followed_ids(db: Session, user_id: int) -> list[int]:
    rows = db.query(models.Follows.followed_id).filter(models.Follows.follower_id == user_id).all()
    return [row[0] for row in rows]


def _score(vote_count: int, created_at: datetime) -> float:
    """log10(votes + 1) rewards more votes but with diminishing returns (10
    votes isn't 10x "hotter" than 1 vote); subtracting age_hours / decay
    steadily drags older posts down the ranking. Tune
    `feed_score_decay_hours` to taste -- smaller = feed churns faster."""
    now = datetime.now(timezone.utc)
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - created).total_seconds() / 3600, 0)
    return math.log10(vote_count + 1) - age_hours / settings.feed_score_decay_hours


def _to_feed_item(post: models.Posts, vote_count: int, score: float | None = None) -> schemas.FeedItem:
    return schemas.FeedItem(
        id=post.id,
        title=post.title,
        content=post.content,
        published=post.published,
        created_at=post.created_at,
        user_id=post.user_id,
        user=schemas.UserResponse.model_validate(post.user),
        vote_count=vote_count,
        score=score,
    )


@router.get("/feed", response_model=schemas.FeedPage, status_code=status.HTTP_200_OK)
def get_feed(
    sort: str = Query("recent", pattern="^(recent|hot)$", description="'recent' = chronological, 'hot' = ranked"),
    limit: int = Query(10, ge=1, le=50),
    cursor: str | None = None,
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    current_user=Depends(oauth2.get_current_user),
):
    followed_ids = _followed_ids(db, current_user.id)
    if not followed_ids:
        # Not an error -- a brand new account with no follows just has an
        # empty feed. Client should fall back to a "discover" view.
        return schemas.FeedPage(items=[], next_cursor=None)

    if sort == "hot":
        return _hot_feed(db, redis_client, current_user.id, followed_ids, limit, cursor)
    return _chronological_feed(db, followed_ids, limit, cursor)


# --- Step 1: chronological (no Redis needed) --------------------------------

def _chronological_feed(db: Session, followed_ids: list[int], limit: int, cursor: str | None) -> schemas.FeedPage:
    query = (
        db.query(models.Posts, func.count(models.Votes.post_id).label("vote_count"))
        .outerjoin(models.Votes, models.Posts.id == models.Votes.post_id)
        .filter(models.Posts.user_id.in_(followed_ids), models.Posts.published.is_(True))
        .group_by(models.Posts.id)
    )

    if cursor:
        parts = decode_cursor(cursor)
        cursor_created_at, cursor_id = datetime.fromisoformat(parts[0]), int(parts[1])
        # Tuple comparison = "strictly older than the last post you saw, or
        # the exact same timestamp but a lower id" -- keeps pagination stable
        # even when two posts share a created_at to the second.
        query = query.filter(tuple_(models.Posts.created_at, models.Posts.id) < (cursor_created_at, cursor_id))

    rows = query.order_by(models.Posts.created_at.desc(), models.Posts.id.desc()).limit(limit).all()

    items = [_to_feed_item(post, vote_count) for post, vote_count in rows]
    next_cursor = None
    if len(rows) == limit:
        last_post, _ = rows[-1]
        next_cursor = encode_cursor(last_post.created_at.isoformat(), last_post.id)

    return schemas.FeedPage(items=items, next_cursor=next_cursor)


# --- Step 2: ranked / "hot", cached in Redis --------------------------------

# How many of the most recent followed posts we're willing to pull from
# Postgres and score in Python per cache miss. Scoring the *entire* history
# every time doesn't scale, and posts older than this are extremely unlikely
# to out-score anything newer on a decay formula anyway.
_CANDIDATE_POOL_SIZE = 300


def _hot_feed(
    db: Session, redis_client: redis.Redis, user_id: int, followed_ids: list[int], limit: int, cursor: str | None
) -> schemas.FeedPage:
    # Cache key pattern from the build plan: feed:{user_id}:{cursor}. Each
    # distinct page (cursor) gets its own cache entry so "page 1" staying
    # warm doesn't depend on "page 2" ever being requested.
    cache_key = f"feed:{user_id}:hot:{cursor or 'start'}"

    cached = redis_client.get(cache_key)
    if cached is not None:
        return schemas.FeedPage.model_validate_json(cached)

    rows = (
        db.query(models.Posts, func.count(models.Votes.post_id).label("vote_count"))
        .outerjoin(models.Votes, models.Posts.id == models.Votes.post_id)
        .filter(models.Posts.user_id.in_(followed_ids), models.Posts.published.is_(True))
        .group_by(models.Posts.id)
        .order_by(models.Posts.created_at.desc())
        .limit(_CANDIDATE_POOL_SIZE)
        .all()
    )

    scored = sorted(
        ((post, vote_count, _score(vote_count, post.created_at)) for post, vote_count in rows),
        key=lambda triple: (triple[2], triple[0].id),
        reverse=True,
    )

    if cursor:
        parts = decode_cursor(cursor)
        cursor_score, cursor_id = float(parts[0]), int(parts[1])
        scored = [t for t in scored if (t[2], t[0].id) < (cursor_score, cursor_id)]

    page = scored[:limit]
    items = [_to_feed_item(post, vote_count, score) for post, vote_count, score in page]

    next_cursor = None
    if len(page) == limit:
        last_post, _, last_score = page[-1]
        next_cursor = encode_cursor(last_score, last_post.id)

    result = schemas.FeedPage(items=items, next_cursor=next_cursor)

    # Short TTL, not "forever": a stale-for-90-seconds feed is an acceptable
    # tradeoff for not recomputing scores on every request; a stale-forever
    # feed is not. See build-plan gotcha and docx "cache invalidation" note.
    redis_client.setex(cache_key, settings.feed_cache_ttl_seconds, result.model_dump_json())
    return result
