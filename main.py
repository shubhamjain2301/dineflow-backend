import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware


# ---------------------------------------------------------------------------
# Lifespan: runs startup/shutdown logic
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialise the SQLite schema
    from models.db import init_db
    await init_db()
    yield
    # Shutdown: nothing to clean up for now


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DineFlow API",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

# In production, FRONTEND_URL should be set to your Vercel URL, e.g.:
#   https://dineflow-frontend-brown.vercel.app
# Multiple origins can be comma-separated: "https://a.vercel.app,https://b.vercel.app"
_frontend_url = os.getenv("FRONTEND_URL", "")
_extra_origins = [o.strip() for o in _frontend_url.split(",") if o.strip()]

ALLOWED_ORIGINS = [
    "http://localhost:3000",        # Next.js dev server
    "https://dineflow-frontend-brown.vercel.app",  # production frontend
    *_extra_origins,                # any additional origins from env var
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Router registration
# ---------------------------------------------------------------------------

# TODO: uncomment each import once the router files are created in task 3.x

from routers.restaurants import router as restaurants_router
app.include_router(restaurants_router, prefix="/api")

from routers.sessions import router as sessions_router
app.include_router(sessions_router, prefix="/api")

from routers.orders import router as orders_router
app.include_router(orders_router, prefix="/api")

# ---------------------------------------------------------------------------
# Health-check endpoint (useful for verifying the server is up)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    from models.db import DB_PATH
    import os
    return {
        "status": "ok",
        "db_path": DB_PATH,
        "db_exists": os.path.exists(DB_PATH),
    }


# ---------------------------------------------------------------------------
# WebSocket endpoints
# ---------------------------------------------------------------------------

from websocket.manager import manager
from websocket.handlers import dispatch
from models.schemas import WsMessage


@app.websocket("/ws/{session_id}")
async def ws_session(ws: WebSocket, session_id: str):
    """Dining Group session room — Requirements: 3.1, 3.2, 3.10, 3.11, 9.3"""
    await manager.connect_session(ws, session_id)

    # If the session isn't in memory (e.g. after a server restart),
    # try to restore it from the database.
    if session_id not in manager.sessions:
        from models.db import get_db
        async with get_db() as db:
            cursor = await db.execute(
                "SELECT id, restaurant_id, invite_link FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

        if row is None:
            # Session truly doesn't exist — reject with 4004
            await ws.close(code=4004)
            return

        # Restore the DiningGroup in memory from DB record
        from models.session import DiningGroup
        manager.sessions[session_id] = DiningGroup(
            session_id=row["id"],
            restaurant_id=row["restaurant_id"],
            invite_link=row["invite_link"],
            participants={},
            cart={},
        )

    # Send an initial sync to the newly connected client.
    from websocket.handlers import _build_sync_payload
    group = manager.sessions[session_id]
    await manager.broadcast_session(session_id, _build_sync_payload(group))

    # Keepalive ping task — sends a ping every 30s to prevent proxy/Render
    # from closing idle WebSocket connections.
    async def _keepalive() -> None:
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    ping_task = asyncio.create_task(_keepalive())

    try:
        while True:
            raw = await ws.receive_text()
            # Ignore pong responses from the client
            if raw.strip() in ('{"type":"pong"}', "pong"):
                continue
            message = WsMessage.model_validate_json(raw)
            await dispatch(message, session_id, ws, manager)
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        await manager.disconnect_session(ws, session_id)
        # If the session still has active connections, broadcast updated sync.
        if session_id in manager.sessions:
            group = manager.sessions[session_id]
            await manager.broadcast_session(session_id, _build_sync_payload(group))


@app.websocket("/ws/dashboard/{restaurant_id}")
async def ws_dashboard(ws: WebSocket, restaurant_id: str):
    """Restaurant Dashboard room — Requirements: 6.3"""
    await manager.connect_dashboard(ws, restaurant_id)

    try:
        while True:
            # Dashboard is receive-only from the client side; just keep alive.
            await ws.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect_dashboard(ws, restaurant_id)


# ---------------------------------------------------------------------------
# Entry point
# Run with: uvicorn main:app --reload  (from the backend/ directory)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
