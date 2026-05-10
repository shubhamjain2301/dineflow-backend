"""
Order endpoints.

Routes:
    POST  /orders                      — confirm and persist a group order
    PATCH /orders/{order_id}/status    — update order status
    GET   /orders?restaurant_id={id}   — list all orders for a restaurant (dashboard)
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from models.db import get_db
from models.schemas import (
    ConfirmOrderRequest,
    GroupOrderResponse,
    OrderItemResponse,
    UpdateStatusRequest,
)
from websocket.manager import manager

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /orders — confirm and persist a group order
# ---------------------------------------------------------------------------

@router.post("/orders")
async def confirm_order(body: ConfirmOrderRequest) -> dict:
    """Persist a confirmed group order and broadcast it to the restaurant dashboard.

    Returns:
        {"id": order_id, "status": "pending"}
    """
    order_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    # Build order items with generated UUIDs
    order_items = [
        {
            "id": str(uuid.uuid4()),
            "order_id": order_id,
            "menu_item_id": item.menu_item_id,
            "participant_id": item.participant_id,
            "display_name": item.display_name,
            "quantity": item.quantity,
            "note": item.note,
        }
        for item in body.items
    ]

    async with get_db() as db:
        # Insert the group order
        await db.execute(
            """
            INSERT INTO group_orders (id, restaurant_id, session_id, eta_minutes, status, created_at)
            VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (order_id, body.restaurant_id, body.session_id, body.eta_minutes, created_at),
        )

        # Insert all order items
        await db.executemany(
            """
            INSERT INTO order_items (id, order_id, menu_item_id, participant_id, display_name, quantity, note)
            VALUES (:id, :order_id, :menu_item_id, :participant_id, :display_name, :quantity, :note)
            """,
            order_items,
        )

        await db.commit()

    # Build the full order object for the broadcast payload
    full_order = {
        "id": order_id,
        "restaurant_id": body.restaurant_id,
        "session_id": body.session_id,
        "eta_minutes": body.eta_minutes,
        "status": "pending",
        "created_at": created_at,
        "items": [
            {
                "id": oi["id"],
                "order_id": order_id,
                "menu_item_id": oi["menu_item_id"],
                "participant_id": oi["participant_id"],
                "display_name": oi["display_name"],
                "quantity": oi["quantity"],
                "note": oi["note"],
            }
            for oi in order_items
        ],
    }

    # Broadcast new order to the restaurant dashboard room
    await manager.broadcast_dashboard(
        body.restaurant_id,
        {"type": "new_order", "payload": full_order},
    )

    return {"id": order_id, "status": "pending"}


# ---------------------------------------------------------------------------
# PATCH /orders/{order_id}/status — update order status
# ---------------------------------------------------------------------------

@router.patch("/orders/{order_id}/status")
async def update_order_status(order_id: str, body: UpdateStatusRequest) -> dict:
    """Update the status of an existing order and broadcast the change.

    Raises:
        HTTPException: 404 if the order does not exist.

    Returns:
        {"id": order_id, "status": new_status}
    """
    async with get_db() as db:
        # Verify the order exists and fetch its restaurant_id
        cursor = await db.execute(
            "SELECT id, restaurant_id FROM group_orders WHERE id = ?",
            (order_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Order not found")

        restaurant_id = row["restaurant_id"]

        # Update the status
        await db.execute(
            "UPDATE group_orders SET status = ? WHERE id = ?",
            (body.status, order_id),
        )
        await db.commit()

    # Broadcast status update to the restaurant dashboard room
    await manager.broadcast_dashboard(
        restaurant_id,
        {
            "type": "status_update",
            "payload": {"order_id": order_id, "status": body.status},
        },
    )

    return {"id": order_id, "status": body.status}


# ---------------------------------------------------------------------------
# GET /orders?restaurant_id={id} — list orders for a restaurant dashboard
# ---------------------------------------------------------------------------

@router.get("/orders", response_model=list[GroupOrderResponse])
async def list_orders(restaurant_id: str = Query(...)) -> list[GroupOrderResponse]:
    """Return all group orders for a restaurant, each with nested order items."""
    async with get_db() as db:
        # Fetch all group orders for the restaurant
        cursor = await db.execute(
            """
            SELECT id, restaurant_id, session_id, eta_minutes, status, created_at
            FROM group_orders
            WHERE restaurant_id = ?
            ORDER BY created_at DESC
            """,
            (restaurant_id,),
        )
        order_rows = await cursor.fetchall()

        if not order_rows:
            return []

        # Collect all order IDs for a single items query
        order_ids = [row["id"] for row in order_rows]
        placeholders = ",".join("?" * len(order_ids))

        cursor = await db.execute(
            f"""
            SELECT id, order_id, menu_item_id, participant_id, display_name, quantity, note
            FROM order_items
            WHERE order_id IN ({placeholders})
            """,
            order_ids,
        )
        item_rows = await cursor.fetchall()

    # Group items by order_id
    items_by_order: dict[str, list[OrderItemResponse]] = {row["id"]: [] for row in order_rows}
    for item in item_rows:
        items_by_order[item["order_id"]].append(
            OrderItemResponse(
                id=item["id"],
                order_id=item["order_id"],
                menu_item_id=item["menu_item_id"],
                participant_id=item["participant_id"],
                display_name=item["display_name"],
                quantity=item["quantity"],
                note=item["note"] or "",
            )
        )

    return [
        GroupOrderResponse(
            id=row["id"],
            restaurant_id=row["restaurant_id"],
            session_id=row["session_id"],
            eta_minutes=row["eta_minutes"],
            status=row["status"],
            created_at=row["created_at"],
            items=items_by_order[row["id"]],
        )
        for row in order_rows
    ]
