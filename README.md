# DineFlow Backend

FastAPI + SQLite backend for the DineFlow MVP.

## Requirements

- Python 3.11+
- Dependencies listed in `requirements.txt`

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Seed the database

Run from the `backend/` directory:

```bash
python seed.py
```

This creates `dineflow.db` and populates it with 5 restaurants and their full menus. The script is idempotent — running it again skips already-inserted restaurants.

### 3. Start the development server

Run from the `backend/` directory:

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/restaurants` | List all restaurants |
| GET | `/api/restaurants/{id}/menu` | Get menu items for a restaurant |
| POST | `/api/sessions` | Create a new dining group session |
| POST | `/api/orders` | Confirm and persist a group order |
| PATCH | `/api/orders/{id}/status` | Update order status |
| GET | `/api/orders?restaurant_id={id}` | List orders for a restaurant |

## WebSocket Endpoints

| Path | Description |
|------|-------------|
| `ws://localhost:8000/ws/{session_id}` | Dining group session room |
| `ws://localhost:8000/ws/dashboard/{restaurant_id}` | Restaurant dashboard room |

## Interactive Docs

Once the server is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
