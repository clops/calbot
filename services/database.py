"""
SQLite persistence layer using aiosqlite.

Schema (single table):
    meals(id, user_id, timestamp, description, calories, input_type)

input_type is either "text" or "photo".
"""

import os
from datetime import datetime, timezone

import aiosqlite

DB_PATH = os.getenv("DB_PATH", "data/calbot.db")

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS meals (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    timestamp  TEXT    NOT NULL,
    description TEXT   NOT NULL,
    calories   INTEGER NOT NULL,
    input_type TEXT    NOT NULL
);
"""


async def init_db() -> None:
    """Create the database and meals table if they don't exist.

    Call once at bot startup (e.g. via Application post_init hook).
    Creates the data/ directory if needed.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        await db.commit()


async def log_meal(
    user_id: int,
    description: str,
    calories: int,
    input_type: str,
) -> None:
    """Insert a meal record for a user.

    Args:
        user_id: Telegram user ID.
        description: Human-readable food description.
        calories: Estimated calorie count.
        input_type: "text" or "photo".
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO meals (user_id, timestamp, description, calories, input_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, timestamp, description, calories, input_type),
        )
        await db.commit()


async def get_today(user_id: int) -> list[dict]:
    """Return all meal records logged today (UTC) for the given user.

    Returns:
        List of dicts with keys: id, user_id, timestamp, description, calories, input_type.
    """
    today = datetime.now(timezone.utc).date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM meals WHERE user_id = ? AND timestamp LIKE ? ORDER BY timestamp",
            (user_id, f"{today}%"),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def delete_last_meal(user_id: int) -> dict | None:
    """Delete the most recent meal for the user and return it, or None if none exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM meals WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        meal = dict(row)
        await db.execute("DELETE FROM meals WHERE id = ?", (meal["id"],))
        await db.commit()
    return meal


async def get_history(user_id: int, days: int = 7) -> list[dict]:
    """Return meal records from the last N days (UTC) for the given user.

    Args:
        user_id: Telegram user ID.
        days: Number of past days to include (default 7).

    Returns:
        List of dicts ordered by timestamp ascending.
    """
    from datetime import timedelta

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM meals WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp",
            (user_id, cutoff),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]
