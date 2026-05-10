"""
Session creation endpoint.

Routes:
    POST /sessions — create a new Dining Group session for a given restaurant
"""

import uuid

from fastapi import APIRouter, HTTPException

from models.db import get_db
from models.schemas import CreateSessionRequest, CreateSessionResponse
from models.session import DiningGroup
from websocket.manager import manager

router = APIRouter()

# Base URL used when building invite links.
# In production this would come from an environment variable.
_FRONTEND_BASE_URL = "http://localhost:3000"


@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(body: CreateSessionRequest) -> CreateSessionResponse:
    """Create a new Dining Group session.

    Validates that the requested restaurant exists, generates a unique
    session ID, stores an in-memory DiningGroup, and returns the session
    ID together with a shareable invite link.

    Raises:
        HTTPException: 404 if the restaurant does not exist in the database.
    """
    # Validate that the restaurant exists
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM restaurants WHERE id = ?", (body.restaurant_id,)
        )
        restaurant = await cursor.fetchone()

    if restaurant is None:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Generate a new session ID and build the invite link
    session_id = str(uuid.uuid4())
    invite_link = f"{_FRONTEND_BASE_URL}/session/{session_id}"

    # Create the DiningGroup and register it in the ConnectionManager
    dining_group = DiningGroup(
        session_id=session_id,
        restaurant_id=body.restaurant_id,
        invite_link=invite_link,
        participants={},
        cart={},
    )
    manager.sessions[session_id] = dining_group

    return CreateSessionResponse(session_id=session_id, invite_link=invite_link)
