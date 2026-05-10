"""
ConnectionManager — manages in-memory Dining Group sessions and WebSocket rooms.

Implements:
  - session rooms: session_id → set[WebSocket]
  - dashboard rooms: restaurant_id → set[WebSocket]
  - in-memory DiningGroup store: session_id → DiningGroup

Requirements: 3.2, 3.10, 3.11, 6.3
"""

import asyncio
import logging

from fastapi import WebSocket

from models.session import DiningGroup

logger = logging.getLogger(__name__)

# Grace period before destroying an empty session (seconds).
# This prevents the session from being wiped when the last participant
# briefly disconnects during a page navigation or network hiccup.
_SESSION_DESTROY_GRACE_SECONDS = 30


class ConnectionManager:
    """Singleton that owns all live Dining Group state and WebSocket rooms.

    Attributes:
        session_rooms:   Maps session_id → set of active WebSocket connections
                         for that Dining Group session.
        dashboard_rooms: Maps restaurant_id → set of active WebSocket connections
                         for that restaurant's dashboard.
        sessions:        Maps session_id → DiningGroup for every active session.
        _destroy_tasks:  Maps session_id → asyncio.Task for pending destroy timers.
    """

    def __init__(self) -> None:
        self.session_rooms: dict[str, set[WebSocket]] = {}
        self.dashboard_rooms: dict[str, set[WebSocket]] = {}
        self.sessions: dict[str, DiningGroup] = {}
        self._destroy_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Session room methods
    # ------------------------------------------------------------------

    async def connect_session(self, ws: WebSocket, session_id: str) -> None:
        """Accept a WebSocket and add it to the session room.

        Also cancels any pending destroy timer for this session (a participant
        reconnected before the grace period expired).
        """
        await ws.accept()

        if session_id not in self.session_rooms:
            self.session_rooms[session_id] = set()
        self.session_rooms[session_id].add(ws)

        # Cancel any pending destroy timer — someone reconnected in time.
        self._cancel_destroy_timer(session_id)

        # Keep DiningGroup.connections in sync so handlers can iterate it.
        if session_id in self.sessions:
            self.sessions[session_id].connections.add(ws)

    async def disconnect_session(self, ws: WebSocket, session_id: str) -> None:
        """Remove a WebSocket from the session room.

        If the room becomes empty, schedules a delayed destroy instead of
        destroying immediately, giving reconnecting clients a grace period.
        """
        room = self.session_rooms.get(session_id)
        if room:
            room.discard(ws)

        if session_id in self.sessions:
            self.sessions[session_id].connections.discard(ws)

        # Schedule delayed destruction when the room is empty.
        if not room or len(room) == 0:
            self._schedule_destroy(session_id)

    def _schedule_destroy(self, session_id: str) -> None:
        """Schedule session destruction after the grace period."""
        self._cancel_destroy_timer(session_id)

        async def _delayed_destroy() -> None:
            await asyncio.sleep(_SESSION_DESTROY_GRACE_SECONDS)
            room = self.session_rooms.get(session_id)
            if not room or len(room) == 0:
                logger.info(
                    "ConnectionManager: destroying empty session %s after grace period.",
                    session_id,
                )
                self.sessions.pop(session_id, None)
                self.session_rooms.pop(session_id, None)
            self._destroy_tasks.pop(session_id, None)

        try:
            loop = asyncio.get_event_loop()
            task = loop.create_task(_delayed_destroy())
            self._destroy_tasks[session_id] = task
        except RuntimeError:
            # No running event loop (e.g. during tests) — destroy immediately.
            self.sessions.pop(session_id, None)
            self.session_rooms.pop(session_id, None)

    def _cancel_destroy_timer(self, session_id: str) -> None:
        """Cancel a pending destroy timer if one exists."""
        task = self._destroy_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

    async def broadcast_session(self, session_id: str, message: dict) -> None:
        """Send a JSON message to every WebSocket in the session room.

        Disconnected sockets are silently removed from the room so they do not
        block future broadcasts (Requirement 3.5, 3.6, 3.7).
        """
        room = self.session_rooms.get(session_id)
        if not room:
            return

        dead: set[WebSocket] = set()
        for ws in list(room):
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning(
                    "broadcast_session: failed to send to a client in session %s; "
                    "marking for removal.",
                    session_id,
                )
                dead.add(ws)

        # Clean up any sockets that failed mid-broadcast.
        for ws in dead:
            room.discard(ws)
            if session_id in self.sessions:
                self.sessions[session_id].connections.discard(ws)

        # If the room is now empty, schedule delayed destruction.
        if not room or len(room) == 0:
            self._schedule_destroy(session_id)

    # ------------------------------------------------------------------
    # Dashboard room methods
    # ------------------------------------------------------------------

    async def connect_dashboard(self, ws: WebSocket, restaurant_id: str) -> None:
        """Accept a WebSocket and add it to the dashboard room for a restaurant."""
        await ws.accept()

        if restaurant_id not in self.dashboard_rooms:
            self.dashboard_rooms[restaurant_id] = set()
        self.dashboard_rooms[restaurant_id].add(ws)

    async def disconnect_dashboard(self, ws: WebSocket, restaurant_id: str) -> None:
        """Remove a WebSocket from the dashboard room for a restaurant."""
        room = self.dashboard_rooms.get(restaurant_id)
        if room:
            room.discard(ws)
            if not room:
                self.dashboard_rooms.pop(restaurant_id, None)

    async def broadcast_dashboard(self, restaurant_id: str, message: dict) -> None:
        """Send a JSON message to every WebSocket in the dashboard room.

        Disconnected sockets are silently removed (Requirement 6.3).
        """
        room = self.dashboard_rooms.get(restaurant_id)
        if not room:
            return

        dead: set[WebSocket] = set()
        for ws in list(room):
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning(
                    "broadcast_dashboard: failed to send to a client for restaurant %s; "
                    "marking for removal.",
                    restaurant_id,
                )
                dead.add(ws)

        for ws in dead:
            room.discard(ws)

        if not room:
            self.dashboard_rooms.pop(restaurant_id, None)


# Module-level singleton — import this instance everywhere.
manager = ConnectionManager()
