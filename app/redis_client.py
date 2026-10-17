"""One Redis connection pool, shared by every feature that needs Redis.

Phase 3 (feed) uses it as a cache. Phase 5 (notifications) points Celery at
the *same* Redis server (different logical DB numbers -- see config.py) as
its broker. Per the build-plan's cross-phase rule: one Redis instance,
multiple uses, never a second Redis just for the job queue.
"""
import redis

from .config import settings

# decode_responses=True means values come back as `str`, not `bytes` -- one
# less `.decode()` call at every call site. Fine for the JSON-text values we
# store here; if you ever cache raw binary you'd want a separate client.
redis_pool = redis.ConnectionPool.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    """FastAPI dependency: `redis_client: redis.Redis = Depends(get_redis)`.

    Pulls a connection from the shared pool rather than opening a new TCP
    connection per request -- same idea as SQLAlchemy's connection pool in
    database.py.
    """
    return redis.Redis(connection_pool=redis_pool)
