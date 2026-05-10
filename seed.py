"""
Seed script for DineFlow MVP.

Populates the SQLite database with 5 restaurants and their menu items.
The script is idempotent: it checks whether each restaurant already exists
by name and skips insertion if it does.

Usage (from the backend/ directory):
    python seed.py
"""

import asyncio
import os
import uuid

import aiosqlite

# ---------------------------------------------------------------------------
# Database path — same resolution logic as models/db.py
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_BACKEND_DIR, "dineflow.db")

# ---------------------------------------------------------------------------
# Schema DDL (mirrors models/db.py so the script is self-contained)
# ---------------------------------------------------------------------------

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS restaurants (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        description TEXT NOT NULL,
        cuisine     TEXT NOT NULL,
        prep_time   INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS menu_items (
        id            TEXT PRIMARY KEY,
        restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
        name          TEXT NOT NULL,
        description   TEXT NOT NULL,
        price         REAL NOT NULL,
        category      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS group_orders (
        id            TEXT PRIMARY KEY,
        restaurant_id TEXT NOT NULL REFERENCES restaurants(id),
        session_id    TEXT NOT NULL,
        eta_minutes   INTEGER,
        status        TEXT NOT NULL DEFAULT 'pending',
        created_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_items (
        id             TEXT PRIMARY KEY,
        order_id       TEXT NOT NULL REFERENCES group_orders(id),
        menu_item_id   TEXT NOT NULL REFERENCES menu_items(id),
        participant_id TEXT NOT NULL,
        display_name   TEXT NOT NULL,
        quantity       INTEGER NOT NULL DEFAULT 1,
        note           TEXT
    )
    """,
]

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

# Each restaurant entry: (name, description, cuisine, prep_time_minutes)
# Each menu item entry:   (name, description, price_usd, category)

RESTAURANTS = [
    {
        "name": "Ember & Oak",
        "description": (
            "A rustic American BBQ joint where slow-smoked meats meet "
            "bold Southern sides. Every rack is hand-rubbed and pit-smoked "
            "for 12+ hours over seasoned oak wood."
        ),
        "cuisine": "American BBQ",
        "prep_time": 25,
        "menu": [
            # Starters
            {
                "name": "Smoked Wings",
                "description": "Hickory-smoked chicken wings tossed in house BBQ sauce, served with ranch dip.",
                "price": 13.50,
                "category": "Starters",
            },
            {
                "name": "Burnt End Bites",
                "description": "Caramelised brisket burnt ends glazed with molasses BBQ sauce.",
                "price": 14.00,
                "category": "Starters",
            },
            # Mains
            {
                "name": "Half Rack Ribs",
                "description": "St. Louis-style pork ribs slow-smoked for 6 hours, served with two sides.",
                "price": 28.00,
                "category": "Mains",
            },
            {
                "name": "Brisket Plate",
                "description": "12-hour oak-smoked beef brisket, sliced to order, with pickles and white bread.",
                "price": 24.00,
                "category": "Mains",
            },
            {
                "name": "Pulled Pork Sandwich",
                "description": "Slow-cooked pulled pork piled high on a brioche bun with coleslaw.",
                "price": 16.00,
                "category": "Mains",
            },
            # Sides
            {
                "name": "Mac & Cheese",
                "description": "Creamy four-cheese macaroni baked with a golden breadcrumb crust.",
                "price": 7.00,
                "category": "Sides",
            },
            {
                "name": "Jalapeño Cornbread",
                "description": "Skillet-baked cornbread with roasted jalapeños and honey butter.",
                "price": 5.50,
                "category": "Sides",
            },
            # Drinks
            {
                "name": "Sweet Tea",
                "description": "House-brewed Southern sweet tea, served over ice with a lemon wedge.",
                "price": 3.50,
                "category": "Drinks",
            },
        ],
    },
    {
        "name": "Sakura Ramen",
        "description": (
            "Authentic Japanese ramen crafted from 18-hour tonkotsu and "
            "shoyu broths. Every bowl is finished tableside with seasonal "
            "toppings and house-made noodles."
        ),
        "cuisine": "Japanese",
        "prep_time": 20,
        "menu": [
            # Starters
            {
                "name": "Gyoza (6 pcs)",
                "description": "Pan-fried pork and cabbage dumplings with ponzu dipping sauce.",
                "price": 9.00,
                "category": "Starters",
            },
            {
                "name": "Edamame",
                "description": "Steamed salted edamame pods, lightly seasoned with sea salt and sesame oil.",
                "price": 5.00,
                "category": "Starters",
            },
            # Mains
            {
                "name": "Tonkotsu Ramen",
                "description": "Rich pork bone broth, chashu pork belly, soft-boiled egg, nori, and bamboo shoots.",
                "price": 17.00,
                "category": "Mains",
            },
            {
                "name": "Spicy Miso Ramen",
                "description": "Fiery red miso broth with ground pork, corn, butter, and a soft-boiled egg.",
                "price": 17.50,
                "category": "Mains",
            },
            {
                "name": "Shoyu Ramen",
                "description": "Clear soy-based chicken broth with chicken chashu, menma, and scallions.",
                "price": 16.00,
                "category": "Mains",
            },
            # Sides
            {
                "name": "Karaage Chicken",
                "description": "Japanese fried chicken marinated in soy and ginger, served with kewpie mayo.",
                "price": 10.00,
                "category": "Sides",
            },
            {
                "name": "Extra Chashu (3 pcs)",
                "description": "Three additional slices of melt-in-your-mouth braised pork belly.",
                "price": 5.50,
                "category": "Sides",
            },
            # Drinks
            {
                "name": "Ramune Soda",
                "description": "Classic Japanese marble soda in original or strawberry flavour.",
                "price": 4.00,
                "category": "Drinks",
            },
        ],
    },
    {
        "name": "La Piazza",
        "description": (
            "A neighbourhood Italian trattoria serving wood-fired Neapolitan "
            "pizzas, hand-rolled pastas, and classic antipasti. Ingredients "
            "are sourced weekly from Italian importers."
        ),
        "cuisine": "Italian",
        "prep_time": 30,
        "menu": [
            # Starters
            {
                "name": "Bruschetta al Pomodoro",
                "description": "Grilled sourdough topped with heirloom tomatoes, fresh basil, and extra-virgin olive oil.",
                "price": 9.50,
                "category": "Starters",
            },
            {
                "name": "Burrata",
                "description": "Creamy burrata with roasted cherry tomatoes, basil oil, and flaky sea salt.",
                "price": 14.00,
                "category": "Starters",
            },
            # Mains
            {
                "name": "Margherita Pizza",
                "description": "San Marzano tomato, fior di latte mozzarella, fresh basil, and olive oil.",
                "price": 18.00,
                "category": "Mains",
            },
            {
                "name": "Cacio e Pepe",
                "description": "Tonnarelli pasta with Pecorino Romano, Parmigiano-Reggiano, and cracked black pepper.",
                "price": 19.00,
                "category": "Mains",
            },
            {
                "name": "Osso Buco",
                "description": "Braised veal shank in white wine and gremolata, served with saffron risotto.",
                "price": 34.00,
                "category": "Mains",
            },
            # Sides
            {
                "name": "Insalata Mista",
                "description": "Mixed greens, shaved fennel, radish, and lemon vinaigrette.",
                "price": 8.00,
                "category": "Sides",
            },
            {
                "name": "Focaccia",
                "description": "Rosemary and sea salt focaccia served warm with whipped ricotta.",
                "price": 6.50,
                "category": "Sides",
            },
            # Drinks
            {
                "name": "San Pellegrino",
                "description": "Sparkling mineral water, 500 ml bottle.",
                "price": 4.00,
                "category": "Drinks",
            },
        ],
    },
    {
        "name": "Spice Route",
        "description": (
            "A vibrant Indian kitchen celebrating the spice trails of "
            "Rajasthan, Punjab, and Kerala. Every dish is made from scratch "
            "using whole spices ground in-house daily."
        ),
        "cuisine": "Indian",
        "prep_time": 35,
        "menu": [
            # Starters
            {
                "name": "Samosa Chaat (2 pcs)",
                "description": "Crispy potato samosas topped with chickpea curry, tamarind chutney, and yoghurt.",
                "price": 10.00,
                "category": "Starters",
            },
            {
                "name": "Tandoori Chicken Tikka",
                "description": "Boneless chicken marinated in yoghurt and spices, charred in the tandoor.",
                "price": 14.50,
                "category": "Starters",
            },
            # Mains
            {
                "name": "Butter Chicken",
                "description": "Tender chicken in a velvety tomato-cream sauce with fenugreek and cardamom.",
                "price": 20.00,
                "category": "Mains",
            },
            {
                "name": "Lamb Rogan Josh",
                "description": "Slow-braised Kashmiri lamb with whole spices, dried chillies, and saffron.",
                "price": 23.00,
                "category": "Mains",
            },
            {
                "name": "Palak Paneer",
                "description": "Fresh cottage cheese cubes in a spiced spinach and cream sauce.",
                "price": 18.00,
                "category": "Mains",
            },
            # Sides
            {
                "name": "Garlic Naan",
                "description": "Tandoor-baked flatbread brushed with garlic butter and fresh coriander.",
                "price": 4.50,
                "category": "Sides",
            },
            {
                "name": "Basmati Rice",
                "description": "Fragrant long-grain basmati rice steamed with whole cardamom and bay leaf.",
                "price": 4.00,
                "category": "Sides",
            },
            # Drinks
            {
                "name": "Mango Lassi",
                "description": "Chilled yoghurt drink blended with Alphonso mango pulp and a pinch of cardamom.",
                "price": 5.50,
                "category": "Drinks",
            },
        ],
    },
    {
        "name": "The Green Bowl",
        "description": (
            "A bright, plant-forward café serving nourishing bowls, wraps, "
            "and smoothies. Everything is 100% vegan, gluten-aware, and "
            "made with locally sourced seasonal produce."
        ),
        "cuisine": "Vegan/Healthy",
        "prep_time": 15,
        "menu": [
            # Starters
            {
                "name": "Hummus & Crudités",
                "description": "House-made roasted garlic hummus with rainbow vegetable sticks and warm pita.",
                "price": 9.00,
                "category": "Starters",
            },
            {
                "name": "Avocado Toast",
                "description": "Smashed avocado on multigrain toast with cherry tomatoes, hemp seeds, and chilli flakes.",
                "price": 11.00,
                "category": "Starters",
            },
            # Mains
            {
                "name": "Buddha Bowl",
                "description": "Quinoa, roasted sweet potato, chickpeas, kale, pickled red cabbage, and tahini dressing.",
                "price": 16.00,
                "category": "Mains",
            },
            {
                "name": "Falafel Wrap",
                "description": "Crispy baked falafel, cucumber, tomato, and tzatziki in a whole-wheat wrap.",
                "price": 13.50,
                "category": "Mains",
            },
            {
                "name": "Lentil & Coconut Soup",
                "description": "Red lentil soup simmered in coconut milk with turmeric, ginger, and lime.",
                "price": 11.00,
                "category": "Mains",
            },
            # Sides
            {
                "name": "Side Salad",
                "description": "Mixed greens, cucumber, cherry tomatoes, and lemon-herb vinaigrette.",
                "price": 6.00,
                "category": "Sides",
            },
            # Drinks
            {
                "name": "Green Smoothie",
                "description": "Spinach, banana, mango, almond milk, and chia seeds blended to order.",
                "price": 7.50,
                "category": "Drinks",
            },
            {
                "name": "Cold Brew Coffee",
                "description": "12-hour cold-steeped single-origin coffee served over ice with oat milk.",
                "price": 5.50,
                "category": "Drinks",
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------

async def seed() -> None:
    """Ensure the schema exists and insert seed data idempotently."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Create tables if they don't exist yet
        for ddl in _DDL:
            await db.execute(ddl)
        await db.commit()

        inserted_restaurants = 0
        inserted_items = 0

        for restaurant in RESTAURANTS:
            # --- Idempotency check: skip if restaurant name already exists ---
            cursor = await db.execute(
                "SELECT id FROM restaurants WHERE name = ?",
                (restaurant["name"],),
            )
            existing = await cursor.fetchone()

            if existing is not None:
                print(f"  [skip] '{restaurant['name']}' already exists.")
                continue

            restaurant_id = str(uuid.uuid4())

            await db.execute(
                """
                INSERT INTO restaurants (id, name, description, cuisine, prep_time)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    restaurant_id,
                    restaurant["name"],
                    restaurant["description"],
                    restaurant["cuisine"],
                    restaurant["prep_time"],
                ),
            )
            inserted_restaurants += 1

            for item in restaurant["menu"]:
                item_id = str(uuid.uuid4())
                await db.execute(
                    """
                    INSERT INTO menu_items (id, restaurant_id, name, description, price, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        restaurant_id,
                        item["name"],
                        item["description"],
                        item["price"],
                        item["category"],
                    ),
                )
                inserted_items += 1

            print(
                f"  [ok]   '{restaurant['name']}' inserted "
                f"({len(restaurant['menu'])} menu items)."
            )

        await db.commit()

        print(
            f"\nSeed complete: {inserted_restaurants} restaurant(s) and "
            f"{inserted_items} menu item(s) inserted."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"Seeding database at: {DB_PATH}\n")
    asyncio.run(seed())
