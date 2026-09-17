"""baseline: users, posts, votes (schema as it exists before Phase 0)

Revision ID: 20725d1142b1
Revises:
Create Date: 2026-09-12 00:00:00.000000

This migration intentionally does NOT create anything -- it's a marker
revision. Your database already has these three tables (created previously
via `Base.metadata.create_all`). Stamp your existing DB to this revision
instead of running it:

    alembic stamp 20725d1142b1

Then run `alembic upgrade head` to apply the Phase 0 / Phase 1 migrations
that follow. If you're setting up a brand-new, empty database instead, flip
the no-ops below to real `op.create_table(...)` calls (or just run
`Base.metadata.create_all` once, then `alembic stamp head`).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20725d1142b1'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op marker revision -- see module docstring.
    pass


def downgrade() -> None:
    # No-op marker revision -- see module docstring.
    pass
