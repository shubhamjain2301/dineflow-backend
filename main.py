import os
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
    return {"status": "ok"}


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

    # Reject connections for sessions that don't exist in memory.
    if session_id not in manager.sessions:
        await ws.close(code=4004)
        return

    # Send an initial sync to the newly connected client.
    from websocket.handlers import _build_sync_payload
    group = manager.sessions[session_id]
    await manager.broadcast_session(session_id, _build_sync_payload(group))

    try:
        while True:
            raw = await ws.receive_text()
            message = WsMessage.model_validate_json(raw)
            await dispatch(message, session_id, ws, manager)
    except WebSocketDisconnect:
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
