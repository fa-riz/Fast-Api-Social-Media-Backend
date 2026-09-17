# Backend — Phase 0 (Auth/Security) + Phase 1 (Comments) + Phase 2 (Follows)

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
alembic upgrade head           # apply the role column, refresh_tokens, comments
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

```bash
uvicorn app.main:app --reload
```

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

## Smoke-tested

29 scenario checks (auth, refresh, ownership on posts, vote-count join,
comment create/reply/edit/soft-delete, cross-post parent rejection, follow/
unfollow, self-follow rejection, duplicate-follow rejection, followers/
following lists, follow-stats counts) all pass against SQLite via FastAPI's
TestClient. Postgres-specific behavior (`now()`, real migrations, the
`CHECK` constraint) should still be verified against a real Postgres
instance before you consider this done — see the docx for exactly what
wasn't (and can't be) covered by the local smoke test.
