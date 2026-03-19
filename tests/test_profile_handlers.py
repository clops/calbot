"""Tests for handlers/profile.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handlers.profile import (
    WEIGHT, HEIGHT, AGE, SEX, ACTIVITY, GOAL,
    cmd_profile, receive_weight, receive_height, receive_age,
    receive_sex, receive_activity, receive_goal, cancel_profile,
)
from tests.conftest import make_update, make_context, make_callback_update


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

class TestCmdProfile:
    async def test_asks_for_weight(self):
        update = make_update()
        result = await cmd_profile(update, make_context())
        assert result == WEIGHT
        reply = update.message.reply_text.call_args.args[0]
        assert "weight" in reply.lower()


# ---------------------------------------------------------------------------
# Text input states
# ---------------------------------------------------------------------------

class TestReceiveWeight:
    async def test_valid_weight(self):
        ctx = make_context()
        result = await receive_weight(make_update(text="85"), ctx)
        assert result == HEIGHT
        assert ctx.user_data["profile_weight"] == 85.0

    async def test_decimal_comma(self):
        ctx = make_context()
        result = await receive_weight(make_update(text="85,5"), ctx)
        assert result == HEIGHT
        assert ctx.user_data["profile_weight"] == 85.5

    async def test_invalid_weight_reprompts(self):
        update = make_update(text="abc")
        result = await receive_weight(update, make_context())
        assert result == WEIGHT

    async def test_out_of_range_reprompts(self):
        update = make_update(text="5")
        result = await receive_weight(update, make_context())
        assert result == WEIGHT


class TestReceiveHeight:
    async def test_valid_height(self):
        ctx = make_context()
        result = await receive_height(make_update(text="180"), ctx)
        assert result == AGE
        assert ctx.user_data["profile_height"] == 180.0

    async def test_invalid_height_reprompts(self):
        result = await receive_height(make_update(text="50"), make_context())
        assert result == HEIGHT


class TestReceiveAge:
    async def test_valid_age(self):
        ctx = make_context()
        result = await receive_age(make_update(text="30"), ctx)
        assert result == SEX
        assert ctx.user_data["profile_age"] == 30

    async def test_invalid_age_reprompts(self):
        result = await receive_age(make_update(text="5"), make_context())
        assert result == AGE


# ---------------------------------------------------------------------------
# Callback query states
# ---------------------------------------------------------------------------

class TestReceiveSex:
    async def test_stores_sex_and_asks_activity(self):
        ctx = make_context()
        update = make_callback_update("profile_sex:male")
        result = await receive_sex(update, ctx)
        assert result == ACTIVITY
        assert ctx.user_data["profile_sex"] == "male"
        update.callback_query.edit_message_text.assert_awaited_once()


class TestReceiveActivity:
    async def test_stores_activity_and_asks_goal(self):
        ctx = make_context()
        update = make_callback_update("profile_activity:moderate")
        result = await receive_activity(update, ctx)
        assert result == GOAL
        assert ctx.user_data["profile_activity"] == "moderate"


class TestReceiveGoal:
    async def test_saves_profile_and_ends(self):
        ctx = make_context()
        ctx.user_data.update({
            "profile_weight": 80.0,
            "profile_height": 180.0,
            "profile_age": 30,
            "profile_sex": "male",
            "profile_activity": "moderate",
        })
        update = make_callback_update("profile_goal:maintain")

        with (
            patch("handlers.profile.database.save_user_profile", new_callable=AsyncMock) as save,
            patch("handlers.profile.calculate_targets", return_value={
                "target_calories": 2759, "target_proteins": 160,
                "target_fats": 77, "target_carbs": 356,
            }),
        ):
            from telegram.ext import ConversationHandler
            result = await receive_goal(update, ctx)

        assert result == ConversationHandler.END
        save.assert_awaited_once()
        reply = update.callback_query.edit_message_text.call_args.args[0]
        assert "2759" in reply
        assert "Profile saved" in reply


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestCancelProfile:
    async def test_cancel_ends_conversation(self):
        from telegram.ext import ConversationHandler
        ctx = make_context()
        ctx.user_data["profile_weight"] = 80.0
        update = make_update()
        result = await cancel_profile(update, ctx)
        assert result == ConversationHandler.END
        assert "profile_weight" not in ctx.user_data
