"""Tests for services/database.py"""

import os
from datetime import datetime, timezone, timedelta

import pytest

import services.database as db_service


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file and ensure data/ dir exists."""
    db_file = tmp_path / "test_calbot.db"
    monkeypatch.setattr(db_service, "DB_PATH", str(db_file))
    return db_file


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

async def test_init_db_creates_file(tmp_db):
    await db_service.init_db()
    assert tmp_db.exists()


async def test_init_db_idempotent(tmp_db):
    """Calling init_db twice must not raise."""
    await db_service.init_db()
    await db_service.init_db()


# ---------------------------------------------------------------------------
# log_meal / get_today
# ---------------------------------------------------------------------------

async def test_log_and_get_today(tmp_db):
    await db_service.init_db()
    await db_service.log_meal(user_id=1, description="banana", calories=90, input_type="text")

    meals = await db_service.get_today(user_id=1)
    assert len(meals) == 1
    assert meals[0]["description"] == "banana"
    assert meals[0]["calories"] == 90
    assert meals[0]["input_type"] == "text"
    assert meals[0]["user_id"] == 1


async def test_get_today_only_returns_current_user(tmp_db):
    await db_service.init_db()
    await db_service.log_meal(1, "apple", 80, "text")
    await db_service.log_meal(2, "burger", 700, "photo")

    meals_user1 = await db_service.get_today(1)
    assert len(meals_user1) == 1
    assert meals_user1[0]["description"] == "apple"

    meals_user2 = await db_service.get_today(2)
    assert len(meals_user2) == 1
    assert meals_user2[0]["description"] == "burger"


async def test_get_today_empty_when_no_meals(tmp_db):
    await db_service.init_db()
    assert await db_service.get_today(42) == []


async def test_get_today_multiple_meals_summed(tmp_db):
    await db_service.init_db()
    await db_service.log_meal(1, "breakfast", 300, "text")
    await db_service.log_meal(1, "lunch", 600, "photo")

    meals = await db_service.get_today(1)
    assert len(meals) == 2
    assert sum(m["calories"] for m in meals) == 900


async def test_meal_timestamp_is_iso_utc(tmp_db):
    await db_service.init_db()
    await db_service.log_meal(1, "test", 100, "text")
    meals = await db_service.get_today(1)
    ts = meals[0]["timestamp"]
    # Must parse without error
    datetime.fromisoformat(ts)


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------

async def test_get_history_returns_recent_meals(tmp_db):
    await db_service.init_db()
    await db_service.log_meal(1, "today's meal", 500, "text")

    history = await db_service.get_history(1, days=7)
    assert len(history) == 1
    assert history[0]["description"] == "today's meal"


async def test_get_history_excludes_old_meals(tmp_db):
    """Insert a meal with a manually backdated timestamp older than 7 days."""
    import aiosqlite

    await db_service.init_db()

    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    async with aiosqlite.connect(db_service.DB_PATH) as db:
        await db.execute(
            "INSERT INTO meals (user_id, timestamp, description, calories, input_type) VALUES (?,?,?,?,?)",
            (1, old_ts, "ancient meal", 999, "text"),
        )
        await db.commit()

    history = await db_service.get_history(1, days=7)
    assert all(m["description"] != "ancient meal" for m in history)


async def test_get_history_empty_for_new_user(tmp_db):
    await db_service.init_db()
    assert await db_service.get_history(99) == []
