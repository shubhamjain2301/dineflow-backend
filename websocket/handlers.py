"""
WebSocket message handlers for DineFlow Dining Group sessions.

The `dispatch` function routes incoming WsMessage objects to the appropriate
handler, mutates the in-memory DiningGroup state, and broadcasts a full `sync`
message to all connected participants.

Requirements: 3.2, 3.4, 3.5, 3.6, 3.7, 4.2
"""

from __future__ import annotations

import dataclasses
import logging

from fastapi import WebSocket

from models.schemas import WsMessage
from models.session import CartItem, DiningGroup, Participant
from websocket.manager import ConnectionManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_sync_payload(group: DiningGroup) -> dict:
    """Build the full-state sync message payload for a DiningGroup."""
    return {
        "type": "sync",
        "payload": {
            "session_id": group.session_id,
            "restaurant_id": group.restaurant_id,
            "invite_link": group.invite_link,
            "participants": [
                {"id": p.id, "display_name": p.display_name}
                for p in group.participants.values()
            ],
            "cart": [dataclasses.asdict(item) for item in group.cart.values()],
            "eta_minutes": group.eta_minutes,
        },
    }


async def _send_error(ws: WebSocket, message: str) -> None:
    """Send an error message back to a single WebSocket connection."""
    try:
        await ws.send_json({"type": "error", "payload": {"message": message}})
    except Exception:
        logger.warning("handlers._send_error: failed to send error to client.")


# ---------------------------------------------------------------------------
# Individual message handlers
# ---------------------------------------------------------------------------


async def _handle_join(
    payload: dict,
    group: DiningGroup,
    session_id: str,
    manager: ConnectionManager,
) -> None:
    """Add a participant to the DiningGroup and broadcast sync.

    Payload: { participant_id: str, display_name: str }
    Requirement: 3.2
    """
    participant_id: str = payload["participant_id"]
    display_name: str = payload["display_name"]

    group.participants[participant_id] = Participant(
        id=participant_id,
        display_name=display_name,
    )

    await manager.broadcast_session(session_id, _build_sync_payload(group))


async def _handle_add_item(
    payload: dict,
    group: DiningGroup,
    session_id: str,
    manager: ConnectionManager,
) -> None:
    """Append a CartItem to the DiningGroup cart and broadcast sync.

    Payload: full CartItem fields
    Requirement: 3.5
    """
    item = CartItem(
        id=payload["id"],
        menu_item_id=payload["menu_item_id"],
        menu_item_name=payload["menu_item_name"],
        price=float(payload["price"]),
        participant_id=payload["participant_id"],
        display_name=payload["display_name"],
        quantity=int(payload.get("quantity", 1)),
        note=payload.get("note", ""),
    )

    group.cart[item.id] = item

    await manager.broadcast_session(session_id, _build_sync_payload(group))


async def _handle_update_item(
    payload: dict,
    group: DiningGroup,
    session_id: str,
    manager: ConnectionManager,
) -> None:
    """Mutate targeted CartItem fields and broadcast sync.

    Payload: { id: str, quantity?: int, note?: str }
    Requirement: 3.6
    """
    item_id: str = payload["id"]
    item = group.cart.get(item_id)

    if item is None:
        logger.warning(
            "handlers._handle_update_item: item %s not found in session %s.",
            item_id,
            session_id,
        )
        return

    if "quantity" in payload:
        item.quantity = int(payload["quantity"])
    if "note" in payload:
        item.note = payload["note"]

    await manager.broadcast_session(session_id, _build_sync_payload(group))


async def _handle_remove_item(
    payload: dict,
    group: DiningGroup,
    session_id: str,
    manager: ConnectionManager,
) -> None:
    """Delete a CartItem by id from the DiningGroup cart and broadcast sync.

    Payload: { id: str }
    Requirement: 3.7
    """
    item_id: str = payload["id"]
    group.cart.pop(item_id, None)

    await manager.broadcast_session(session_id, _build_sync_payload(group))


async def _handle_set_eta(
    payload: dict,
    group: DiningGroup,
    session_id: str,
    manager: ConnectionManager,
) -> None:
    """Set the DiningGroup ETA and broadcast sync.

    Payload: { eta_minutes: int }
    Requirement: 4.2
    """
    group.eta_minutes = int(payload["eta_minutes"])

    await manager.broadcast_session(session_id, _build_sync_payload(group))


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


async def dispatch(
    message: WsMessage,
    session_id: str,
    ws: WebSocket,
    manager: ConnectionManager,
) -> None:
    """Route an incoming WebSocket message to the appropriate handler.

    If the session does not exist in manager.sessions, an error is sent back
    to the caller and the function returns immediately.

    Unknown message types result in an error sent back to the caller only
    (not broadcast).

    Requirements: 3.2, 3.4, 3.5, 3.6, 3.7, 4.2
    """
    group = manager.sessions.get(session_id)
    if group is None:
        logger.warning(
            "dispatch: session %s not found in manager.sessions.", session_id
        )
        await _send_error(ws, "Session not found")
        return

    msg_type = message.type
    payload = message.payload

    if msg_type == "join":
        await _handle_join(payload, group, session_id, manager)

    elif msg_type == "add_item":
        await _handle_add_item(payload, group, session_id, manager)

    elif msg_type == "update_item":
        await _handle_update_item(payload, group, session_id, manager)

    elif msg_type == "remove_item":
        await _handle_remove_item(payload, group, session_id, manager)

    elif msg_type == "set_eta":
        await _handle_set_eta(payload, group, session_id, manager)

    else:
        logger.warning(
            "dispatch: unknown message type %r in session %s.", msg_type, session_id
        )
        await _send_error(ws, "Unknown message type")
