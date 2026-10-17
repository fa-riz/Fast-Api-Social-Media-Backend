"""Phase 6 — tracks which users currently have an open WebSocket connection,
so a new message can be pushed to them the instant it's sent instead of
waiting for the recipient to poll or reload.

This is an in-memory, single-process implementation: the connection table
below is just a Python dict living in this worker process' memory. That's
the right amount of complexity for one `uvicorn` process. The moment you run
more than one process (multiple uvicorn workers, multiple machines behind a
load balancer), process B has no idea process A is holding a socket open for
user 42 -- see the docx's "scaling WebSockets past one process" section for
the fix (a shared pub/sub layer, e.g. Redis Pub/Sub, so every process can
broadcast to every other process' connections).
"""
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # One user can have the app open in multiple tabs/devices at once,
        # so each user maps to a SET of sockets, not a single socket.
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id].add(websocket)
        logger.info("WS connected: user_id=%s (now %d socket(s))", user_id, len(self._connections[user_id]))

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        self._connections[user_id].discard(websocket)
        if not self._connections[user_id]:
            del self._connections[user_id]

    async def send_to_user(self, user_id: int, payload: dict) -> None:
        """Best-effort push. If the user has no open socket right now, this
        is silently a no-op -- they'll see the message next time they load
        the conversation over REST. The database row already exists by the
        time this runs, so a missed push never loses data, it just loses the
        "instant" part of real-time delivery for that one moment."""
        dead: list[WebSocket] = []
        for ws in self._connections.get(user_id, set()):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)


# One shared instance for the whole process -- every request handler and the
# WebSocket route itself import this same `manager`, the same way every
# request shares one SQLAlchemy engine from database.py.
manager = ConnectionManager()
