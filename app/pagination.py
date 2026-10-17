"""Opaque cursor pagination, shared by the feed (Phase 3) and message history
(Phase 6) -- see the build plan's "Pagination: cursor-based everywhere past
Phase 2" cross-phase rule.

Why not offset pagination (`?skip=20&limit=10`)? Offset pagination re-counts
and re-skips rows on every request, which gets slow on large tables, and
rows shift under you if something new gets inserted while a user is
paging (they see a duplicate or miss a row). Cursor pagination instead says
"give me the 10 rows that come after *this specific row*", which is both
faster (an indexed `WHERE (col, id) < (?, ?)` instead of `OFFSET 20000`) and
stable while new data arrives ahead of the cursor.

The cursor itself is just "the sort key values of the last row you saw",
opaque-encoded so the client treats it as a black box token instead of
constructing one by hand.
"""
import base64


def encode_cursor(*parts) -> str:
    """Pack arbitrary sort-key values into one opaque, URL-safe string.

    Example: encode_cursor(post.created_at.isoformat(), post.id)
    -> "MjAyNi0wOS0yMFQxMjowMDowMHwxMjM="
    """
    raw = "|".join(str(p) for p in parts)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> list[str]:
    """Reverse of encode_cursor. Returns the raw string parts -- the caller
    converts each one back to the right type (datetime.fromisoformat, int,
    float, ...) since this module doesn't know the shape of any given
    cursor."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        return raw.split("|")
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        raise ValueError("Invalid or corrupted cursor") from exc
