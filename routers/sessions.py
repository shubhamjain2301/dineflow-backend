"""
Session creation endpoint.

Routes:
    POST /sessions — create a new Dining Group session for a given restaurant
"""

import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from models.db import get_db
from models.schemas import CreateSessionRequest, CreateSessionResponse
from models.session import DiningGroup
from websocket.manager import manager

router = APIRouter()

# Base URL used when building invite links.
_FRONTEND_BASE_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    """Create a new Dining Group session.

    Persists the session to the database so it survives server restarts,
    then registers it in the in-memory ConnectionManager.

    Raises:
        HTTPException: 404 if the restaurant does not exist.
    """
    async with get_db() as db:
        # Validate restaurant exists
        cursor = await db.execute(
            "SELECT id FROM restaurants WHERE id = ?", (body.restaurant_id,)
        )
        restaurant = await cursor.fetchone()

        if restaurant is None:
            raise HTTPException(status_code=404, detail="Restaurant not found")

        session_id = str(uuid.uuid4())
        invite_link = f"{_FRONTEND_BASE_URL}/session/{session_id}"
        created_at = datetime.utcnow().isoformat()

        # Persist to DB so the session survives server restarts
        await db.execute(
            "INSERT INTO sessions (id, restaurant_id, invite_link, created_at) VALUES (?, ?, ?, ?)",
            (session_id, body.restaurant_id, invite_link, created_at),
        )
        await db.commit()

    # Register in-memory DiningGroup
    dining_group = DiningGroup(
        session_id=session_id,
        restaurant_id=body.restaurant_id,
        invite_link=invite_link,
        participants={},
        cart={},
    )
    manager.sessions[session_id] = dining_group

    return CreateSessionResponse(session_id=session_id, invite_link=invite_link)
