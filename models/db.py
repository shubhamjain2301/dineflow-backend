"""
Async SQLite connection factory and schema initialisation for DineFlow.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aiosqlite

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

# Resolve the path relative to this file so it always lands in backend/
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_BACKEND_DIR, "dineflow.db")


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager that yields an open aiosqlite connection.

    Usage::

        async with get_db() as db:
            await db.execute("SELECT ...")
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Enable foreign-key enforcement for this connection
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_CREATE_RESTAURANTS = """
CREATE TABLE IF NOT EXISTS restaurants (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    cuisine     TEXT NOT NULL,
    prep_time   INTEGER NOT NULL
);
"""

_CREATE_MENU_ITEMS = """
CREATE TABLE IF NOT EXISTS menu_items (
    id            TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
    name          TEXT NOT NULL,
    description   TEXT NOT NULL,
    price         REAL NOT NULL,
    category      TEXT NOT NULL
);
"""

_CREATE_GROUP_ORDERS = """
CREATE TABLE IF NOT EXISTS group_orders (
    id            TEXT PRIMARY KEY,
    restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
    session_id    TEXT NOT NULL,
    eta_minutes   INTEGER,
    status        TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL
);
"""

_CREATE_ORDER_ITEMS = """
CREATE TABLE IF NOT EXISTS order_items (
    id             TEXT PRIMARY KEY,
    order_id       TEXT NOT NULL REFERENCES group_orders(id),
    menu_item_id   TEXT NOT NULL REFERENCES menu_items(id),
    participant_id TEXT NOT NULL,
    display_name   TEXT NOT NULL,
    quantity       INTEGER NOT NULL DEFAULT 1,
    note           TEXT
);
"""


async def init_db() -> None:
    """Create all four tables if they do not already exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(_CREATE_RESTAURANTS)
        await db.execute(_CREATE_MENU_ITEMS)
        await db.execute(_CREATE_GROUP_ORDERS)
        await db.execute(_CREATE_ORDER_ITEMS)
        await db.commit()
