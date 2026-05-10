"""
Restaurant and menu endpoints.

Routes:
    GET /restaurants          — list all restaurants
    GET /restaurants/{id}/menu — list menu items for a restaurant (404 if not found)
"""

from fastapi import APIRouter, HTTPException

from models.db import get_db
from models.schemas import MenuItemResponse, RestaurantResponse

router = APIRouter()


@router.get("/restaurants", response_model=list[RestaurantResponse])
async def list_restaurants() -> list[RestaurantResponse]:
    """Return all restaurants from the database."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, description, cuisine, prep_time FROM restaurants"
        )
        rows = await cursor.fetchall()

    return [
        RestaurantResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            cuisine=row["cuisine"],
            prep_time=row["prep_time"],
        )
        for row in rows
    ]


@router.get("/restaurants/{restaurant_id}/menu", response_model=list[MenuItemResponse])
async def get_restaurant_menu(restaurant_id: str) -> list[MenuItemResponse]:
    """Return all menu items for the given restaurant.

    Raises:
        HTTPException: 404 if the restaurant does not exist.
    """
    async with get_db() as db:
        # Verify the restaurant exists
        cursor = await db.execute(
            "SELECT id FROM restaurants WHERE id = ?", (restaurant_id,)
        )
        restaurant = await cursor.fetchone()

        if restaurant is None:
            raise HTTPException(status_code=404, detail="Restaurant not found")

        # Fetch menu items
        cursor = await db.execute(
            "SELECT id, restaurant_id, name, description, price, category"
            " FROM menu_items WHERE restaurant_id = ?",
            (restaurant_id,),
        )
        rows = await cursor.fetchall()

    return [
        MenuItemResponse(
            id=row["id"],
            restaurant_id=row["restaurant_id"],
            name=row["name"],
            description=row["description"],
            price=row["price"],
            category=row["category"],
        )
        for row in rows
    ]
