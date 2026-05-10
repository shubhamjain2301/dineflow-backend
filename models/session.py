"""
In-memory session models for DineFlow Dining Group state.

These dataclasses represent the ephemeral state of a live Dining Group session.
No database writes occur until order confirmation — all session state lives here.
"""

from dataclasses import dataclass, field


@dataclass
class CartItem:
    id: str                  # client-generated UUID
    menu_item_id: str
    menu_item_name: str
    price: float
    participant_id: str
    display_name: str
    quantity: int = 1
    note: str = ""


@dataclass
class Participant:
    id: str                  # client-generated UUID
    display_name: str


@dataclass
class DiningGroup:
    session_id: str
    restaurant_id: str
    invite_link: str
    participants: dict[str, Participant]   # keyed by participant_id
    cart: dict[str, CartItem]              # keyed by cart_item_id
    eta_minutes: int | None = None
    connections: set = field(default_factory=set)  # set of WebSocket connections
