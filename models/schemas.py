"""
Pydantic request/response schemas for the DineFlow API.

These models are used for request validation and response serialization
across all REST endpoints and WebSocket message handling.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Session schemas
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    restaurant_id: str


class CreateSessionResponse(BaseModel):
    session_id: str
    invite_link: str


# ---------------------------------------------------------------------------
# WebSocket message envelope
# ---------------------------------------------------------------------------

class WsMessage(BaseModel):
    type: str   # join | leave | add_item | update_item | remove_item | set_eta | sync
    payload: dict


# ---------------------------------------------------------------------------
# Order schemas
# ---------------------------------------------------------------------------

class OrderItemPayload(BaseModel):
    menu_item_id: str
    menu_item_name: str
    price: float
    participant_id: str
    display_name: str
    quantity: int
    note: str = ""


class ConfirmOrderRequest(BaseModel):
    session_id: str
    restaurant_id: str
    eta_minutes: Optional[int] = None
    items: list[OrderItemPayload]


class UpdateStatusRequest(BaseModel):
    status: Literal["pending", "preparing", "ready"]


# ---------------------------------------------------------------------------
# Restaurant and menu response schemas
# ---------------------------------------------------------------------------

class RestaurantResponse(BaseModel):
    id: str
    name: str
    description: str
    cuisine: str
    prep_time: int


class MenuItemResponse(BaseModel):
    id: str
    restaurant_id: str
    name: str
    description: str
    price: float
    category: str


# ---------------------------------------------------------------------------
# Order response schemas
# ---------------------------------------------------------------------------

class OrderItemResponse(BaseModel):
    id: str
    order_id: str
    menu_item_id: str
    participant_id: str
    display_name: str
    quantity: int
    note: str


class GroupOrderResponse(BaseModel):
    id: str
    restaurant_id: str
    session_id: str
    eta_minutes: Optional[int]
    status: str
    created_at: str
    items: list[OrderItemResponse]
