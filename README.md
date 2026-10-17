# Backend — Phase 0 (Auth/Security) + Phase 1 (Comments) + Phase 2 (Follows)
# + Phase 3 (Feed) + Phase 4 (Media) + Phase 5 (Notifications) + Phase 6 (DMs)

## Setup

```bash
python -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env            # then fill in DATABASE_URL and SECRET_KEY
```

Generate a real secret key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Database migrations (Alembic)

**If you already have an existing database** (users/posts/votes tables from
before this change):
```bash
alembic stamp 20725d1142b1     # mark your DB as "already at the baseline"
alembic upgrade head           # apply everything through Phase 6
```

**If you're starting from a brand-new, empty database:**
```bash
alembic upgrade head           # runs the baseline no-op, then creates everything
```
(Baseline is a no-op migration either way — see the docstring in
`alembic/versions/..._baseline_users_posts_votes.py` if you want it to
actually create the original three tables on a truly empty DB instead of
relying on `create_all`.)

Going forward, whenever you change `app/models.py`:
```bash
alembic revision --autogenerate -m "short description"
alembic upgrade head
```

## Run

Phase 3 (feed cache) and Phase 5 (notifications) need Redis running. Easiest
local option is Docker:
```bash
docker run -p 6379:6379 redis:7
```

Start the API:
```bash
uvicorn app.main:app --reload
```

Phase 5 also needs a Celery worker running alongside the API -- notifications
are enqueued by the API process but *created* by the worker process:
```bash
celery -A app.celery_app worker --loglevel=info
```

Phase 4 (media uploads) needs real S3/R2/MinIO credentials in `.env` to
actually generate working pre-signed URLs; without them the endpoints still
run but any real upload attempt will fail against a fake bucket.

Phase 6 (direct messaging) needs nothing extra to run locally -- the
WebSocket endpoint (`/ws/messages`) is served by the same `uvicorn` process
as everything else.

## What changed

See the accompanying docx (`phase-0-1-implementation-notes.docx`) for the
full write-up: what was fixed, why, the theory behind refresh tokens /
threaded comments / soft-deletes, and gotchas to watch for in later phases.

Short version:

**Phase 0**
- Alembic wired up (`alembic/`), pointed at `app.config.settings` / `app.models`.
- `Users.role` column (`user` / `mod` / `admin`, default `user`).
- Secret key + JWT algorithm + token lifetimes moved into `Settings` (env-backed) — no more hardcoded secret in `oauth2.py`.
- Refresh tokens: `RefreshTokens` table, `/login` now returns `access_token` + `refresh_token`, new `/login/refresh` endpoint. Only a SHA-256 hash of the token is ever stored.
- `PUT /posts/{id}`: ownership now checked against the authenticated user; `user_id`/`id` removed from the request body.
- `DELETE /posts/{id}`: null-checked before the ownership check → 404 instead of a raw 500.
- `GET /posts`: switched to `outerjoin` so posts with zero votes still show up, and dropped an accidental filter that had silently restricted the whole feed to posts *you'd* voted on.

**Phase 1**
- `Comments` table: flat structure, `parent_id` self-FK for replies, `is_deleted` for soft delete.
- `POST/GET /posts/{post_id}/comments`, `PUT/DELETE /comments/{id}`.
- Soft delete blanks content + flags `is_deleted`, keeps the row so replies under it don't orphan.

**Phase 2**
- `Follows` table: composite PK `(follower_id, followed_id)` — prevents duplicate follows without a redundant unique index — plus a DB-level `CHECK (follower_id != followed_id)`.
- `POST/DELETE /users/{id}/follow` (follow / unfollow), `GET /users/{id}/followers`, `GET /users/{id}/following` (both paginated, `limit`/`skip`), `GET /users/{id}/follow-stats` (counts — flagged as a Phase 3 Redis-cache candidate).

**Phase 3**
- `GET /feed?sort=recent` — chronological feed of posts from people you follow, cursor-paginated (`created_at` + `id`).
- `GET /feed?sort=hot` — ranked feed (`log10(votes+1) - age_hours/decay`), cached in Redis per `feed:{user_id}:hot:{cursor}` with a short TTL (`FEED_CACHE_TTL_SECONDS`).
- No new tables — reads `Posts`/`Votes`/`Follows`, caches computed results in Redis instead of Postgres.

**Phase 4**
- `Media` table: CDN url, S3 object key, optional `post_id`.
- `POST /media/upload-url` — validates content-type, returns a pre-signed S3/R2 PUT url. `POST /media` — client confirms the upload finished, we persist the row. FastAPI never touches file bytes.

**Phase 5**
- `Notifications` table (`type`/`target_type` as plain strings, `target_id` polymorphic — not a FK).
- Celery + Redis job queue. `comments.py`/`follows.py` enqueue via `.delay()`, never write synchronously in the request path. `GET /notifications`, `GET /notifications/unread-count`, `PATCH /notifications/{id}/read`.

**Phase 6**
- `Conversations` / `ConversationParticipants` (join table, group-DM-ready) / `Messages`.
- `POST/GET /conversations`, `GET/POST /conversations/{id}/messages` (cursor-paginated, same pattern as the feed), `PATCH /conversations/{id}/read`.
- `WS /ws/messages?token=<access_token>` — push-only real-time delivery. Sending is still a normal REST POST; the socket exists purely so the *other* participant sees it arrive immediately when they're online.

## Smoke-tested

29 scenario checks against Phases 0–2 (auth, refresh, ownership on posts,
vote-count join, comment create/reply/edit/soft-delete, cross-post parent
rejection, follow/unfollow, self-follow rejection, duplicate-follow
rejection, followers/following lists, follow-stats counts) all pass against
SQLite via FastAPI's TestClient — see the docx for what Postgres-specific
behavior (`now()`, real migrations, the `CHECK` constraint) still needs
verifying against real Postgres.

Phases 3–6 were checked with a SQLite + `fakeredis` + mocked-Celery smoke
pass (import sanity, feed cursor pagination and cache read/write, media
upload-url validation, notification enqueue-on-comment/follow, conversation
creation/ownership and message cursor pagination). Redis, a live Celery
worker, and a real S3/R2 bucket still need to be exercised for real before
you'd call this done — see the docx's "what wasn't tested" note for each phase.
