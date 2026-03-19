"""
SQLite persistence layer using aiosqlite.

Tables:
    meals(id, user_id, timestamp, description, calories, input_type, proteins, fats, carbohydrates)
    user_settings(user_id, show_calories, show_proteins, show_fats, show_carbohydrates)

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
    Creates the data/ directory if needed. Also migrates existing databases
    to add macro columns if absent.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        # Migrate: add macro columns to existing databases
        async with db.execute("PRAGMA table_info(meals)") as cursor:
            columns = {row[1] for row in await cursor.fetchall()}
        for col in ("proteins", "fats", "carbohydrates"):
            if col not in columns:
                await db.execute(f"ALTER TABLE meals ADD COLUMN {col} INTEGER DEFAULT NULL")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS user_settings ("
            "user_id INTEGER PRIMARY KEY, "
            "show_calories INTEGER NOT NULL DEFAULT 1, "
            "show_proteins INTEGER NOT NULL DEFAULT 1, "
            "show_fats INTEGER NOT NULL DEFAULT 1, "
            "show_carbohydrates INTEGER NOT NULL DEFAULT 1)"
        )
        # Migrate: add reminder and language columns to user_settings
        async with db.execute("PRAGMA table_info(user_settings)") as cursor:
            settings_cols = {row[1] for row in await cursor.fetchall()}
        if "show_reminders" not in settings_cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN show_reminders INTEGER NOT NULL DEFAULT 0")
        if "language_code" not in settings_cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN language_code TEXT DEFAULT NULL")
        if "language_manual" not in settings_cols:
            await db.execute("ALTER TABLE user_settings ADD COLUMN language_manual INTEGER NOT NULL DEFAULT 0")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS user_profiles ("
            "user_id INTEGER PRIMARY KEY, "
            "weight_kg REAL NOT NULL, "
            "height_cm REAL NOT NULL, "
            "age INTEGER NOT NULL, "
            "sex TEXT NOT NULL, "
            "activity_level TEXT NOT NULL, "
            "goal TEXT NOT NULL, "
            "target_calories INTEGER NOT NULL, "
            "target_proteins INTEGER NOT NULL, "
            "target_fats INTEGER NOT NULL, "
            "target_carbs INTEGER NOT NULL)"
        )
        await db.commit()


async def log_meal(
    user_id: int,
    description: str,
    calories: int,
    input_type: str,
    proteins: int | None = None,
    fats: int | None = None,
    carbohydrates: int | None = None,
) -> None:
    """Insert a meal record for a user.

    Args:
        user_id: Telegram user ID.
        description: Human-readable food description.
        calories: Estimated calorie count.
        input_type: "text" or "photo".
        proteins: Estimated protein in grams.
        fats: Estimated fat in grams.
        carbohydrates: Estimated carbohydrates in grams.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO meals (user_id, timestamp, description, calories, input_type, proteins, fats, carbohydrates) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, timestamp, description, calories, input_type, proteins, fats, carbohydrates),
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


_SETTINGS_FIELDS = frozenset({"show_calories", "show_proteins", "show_fats", "show_carbohydrates", "show_reminders"})

_SETTINGS_DEFAULTS = {
    "show_calories": True,
    "show_proteins": True,
    "show_fats": True,
    "show_carbohydrates": True,
    "show_reminders": False,
}


async def get_user_settings(user_id: int) -> dict:
    """Return display settings for a user, defaulting to all-True if no row exists."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if row is None:
        result = dict(_SETTINGS_DEFAULTS)
        result["language_code"] = None
        result["language_manual"] = False
        return result
    d = dict(row)
    result = {field: bool(d[field]) for field in _SETTINGS_FIELDS if field in d}
    # Backfill defaults for columns added by migration
    for field, default in _SETTINGS_DEFAULTS.items():
        if field not in result:
            result[field] = default
    result["language_code"] = d.get("language_code")
    result["language_manual"] = bool(d.get("language_manual", 0))
    return result


async def toggle_setting(user_id: int, field: str) -> bool:
    """Toggle a single display setting for a user. Returns the new value.

    Raises ValueError if field is not a valid settings column.
    """
    if field not in _SETTINGS_FIELDS:
        raise ValueError(f"Invalid setting: {field}")

    async with aiosqlite.connect(DB_PATH) as db:
        # Ensure row exists with defaults
        await db.execute(
            "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,)
        )
        # Flip the value: 1 -> 0, 0 -> 1
        await db.execute(
            f"UPDATE user_settings SET {field} = NOT {field} WHERE user_id = ?",
            (user_id,),
        )
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
        await db.commit()
    return bool(dict(row)[field])


async def save_user_profile(
    user_id: int,
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    goal: str,
    targets: dict,
) -> None:
    """Insert or update a user's profile and pre-computed targets."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_profiles "
            "(user_id, weight_kg, height_cm, age, sex, activity_level, goal, "
            "target_calories, target_proteins, target_fats, target_carbs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id, weight_kg, height_cm, age, sex, activity_level, goal,
                targets["target_calories"], targets["target_proteins"],
                targets["target_fats"], targets["target_carbs"],
            ),
        )
        await db.commit()


async def get_user_profile(user_id: int) -> dict | None:
    """Return a user's profile and targets, or None if not set."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
    return dict(row) if row else None


async def update_language(user_id: int, language_code: str) -> None:
    """Store the user's Telegram language_code in settings (upsert)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_settings (user_id, language_code) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET language_code = excluded.language_code",
            (user_id, language_code),
        )
        await db.commit()


async def set_language(user_id: int, language_code: str) -> None:
    """Explicitly set the user's language (manual override). Sets language_manual=1."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO user_settings (user_id, language_code, language_manual) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET language_code = excluded.language_code, language_manual = 1",
            (user_id, language_code),
        )
        await db.commit()


async def get_reminder_users() -> list[dict]:
    """Return user_id and language_code for all users with reminders enabled."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_id, language_code FROM user_settings WHERE show_reminders = 1"
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(row) for row in rows]
