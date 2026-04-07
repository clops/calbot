"""Tests for handlers/aims.py"""

from unittest.mock import AsyncMock, patch

import pytest
from telegram.ext import ConversationHandler

from handlers.aims import (
    AIMS_CALORIES, AIMS_PROTEINS, AIMS_FATS, AIMS_CARBS,
    cmd_aims, receive_calories, receive_proteins, receive_fats,
    receive_carbs, cancel_aims,
)
from tests.conftest import make_update, make_context

_AUTO_SETTINGS = {
    "language_manual": False,
    "language_code": None,
}

_ALL_SHOWN = {
    "show_calories": True,
    "show_proteins": True,
    "show_fats": True,
    "show_carbohydrates": True,
    "show_reminders": False,
    "language_code": None,
    "language_manual": False,
}

_ONLY_CALORIES = {
    **_ALL_SHOWN,
    "show_proteins": False,
    "show_fats": False,
    "show_carbohydrates": False,
}

_NO_CALORIES = {
    **_ALL_SHOWN,
    "show_calories": False,
}

_NONE_ENABLED = {
    **_ALL_SHOWN,
    "show_calories": False,
    "show_proteins": False,
    "show_fats": False,
    "show_carbohydrates": False,
}


@pytest.fixture(autouse=True)
def _mock_resolve_language_deps():
    """Mock database calls used by resolve_language so aims tests don't need a real DB."""
    with (
        patch("utils.helpers.database.get_user_settings", new_callable=AsyncMock, return_value=_AUTO_SETTINGS),
        patch("utils.helpers.database.update_language", new_callable=AsyncMock),
        patch("handlers.aims.database.get_user_profile", new_callable=AsyncMock, return_value=None),
    ):
        yield


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

class TestCmdAims:
    async def test_asks_for_calories_when_all_shown(self):
        update = make_update()
        ctx = make_context()
        with patch("handlers.aims.database.get_user_settings", new_callable=AsyncMock, return_value=_ALL_SHOWN):
            result = await cmd_aims(update, ctx)
        assert result == AIMS_CALORIES
        reply = update.message.reply_text.call_args.args[0]
        assert "calorie" in reply.lower()

    async def test_skips_calories_when_disabled(self):
        update = make_update()
        ctx = make_context()
        with patch("handlers.aims.database.get_user_settings", new_callable=AsyncMock, return_value=_NO_CALORIES):
            result = await cmd_aims(update, ctx)
        assert result == AIMS_PROTEINS
        reply = update.message.reply_text.call_args.args[0]
        assert "protein" in reply.lower()

    async def test_shows_current_value_in_prompt(self):
        update = make_update()
        ctx = make_context()
        existing = {"target_calories": 2200, "target_proteins": 150, "target_fats": 70, "target_carbs": 250}
        with (
            patch("handlers.aims.database.get_user_settings", new_callable=AsyncMock, return_value=_ALL_SHOWN),
            patch("handlers.aims.database.get_user_profile", new_callable=AsyncMock, return_value=existing),
        ):
            result = await cmd_aims(update, ctx)
        assert result == AIMS_CALORIES
        reply = update.message.reply_text.call_args.args[0]
        assert "2200" in reply

    async def test_nothing_enabled_ends(self):
        update = make_update()
        ctx = make_context()
        with patch("handlers.aims.database.get_user_settings", new_callable=AsyncMock, return_value=_NONE_ENABLED):
            result = await cmd_aims(update, ctx)
        assert result == ConversationHandler.END
        reply = update.message.reply_text.call_args.args[0]
        assert "disabled" in reply.lower() or "deaktiviert" in reply.lower()


# ---------------------------------------------------------------------------
# Calories
# ---------------------------------------------------------------------------

class TestReceiveCalories:
    async def test_valid_calories(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_calories(make_update(text="2200"), ctx)
        assert result == AIMS_PROTEINS
        assert ctx.user_data["aims_calories"] == 2200

    async def test_invalid_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_calories(make_update(text="abc"), ctx)
        assert result == AIMS_CALORIES

    async def test_too_low_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_calories(make_update(text="100"), ctx)
        assert result == AIMS_CALORIES

    async def test_too_high_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_calories(make_update(text="20000"), ctx)
        assert result == AIMS_CALORIES


# ---------------------------------------------------------------------------
# Proteins
# ---------------------------------------------------------------------------

class TestReceiveProteins:
    async def test_valid(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_proteins(make_update(text="150"), ctx)
        assert result == AIMS_FATS
        assert ctx.user_data["aims_proteins"] == 150

    async def test_invalid_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_proteins(make_update(text="abc"), ctx)
        assert result == AIMS_PROTEINS

    async def test_out_of_range_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_proteins(make_update(text="1500"), ctx)
        assert result == AIMS_PROTEINS


# ---------------------------------------------------------------------------
# Fats
# ---------------------------------------------------------------------------

class TestReceiveFats:
    async def test_valid(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_fats(make_update(text="70"), ctx)
        assert result == AIMS_CARBS
        assert ctx.user_data["aims_fats"] == 70

    async def test_invalid_reprompts(self):
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        result = await receive_fats(make_update(text="abc"), ctx)
        assert result == AIMS_FATS


# ---------------------------------------------------------------------------
# Carbs
# ---------------------------------------------------------------------------

class TestReceiveCarbs:
    async def test_saves_and_ends(self):
        ctx = make_context()
        ctx.user_data.update({
            "aims_settings": _ALL_SHOWN,
            "aims_calories": 2200,
            "aims_proteins": 150,
            "aims_fats": 70,
        })
        update = make_update(text="250")

        with patch("handlers.aims.database.save_user_aims", new_callable=AsyncMock) as save:
            result = await receive_carbs(update, ctx)

        assert result == ConversationHandler.END
        save.assert_awaited_once_with(
            user_id=1,
            target_calories=2200,
            target_proteins=150,
            target_fats=70,
            target_carbs=250,
        )
        reply = update.message.reply_text.call_args.args[0]
        assert "2200" in reply
        assert "Targets saved" in reply

    async def test_invalid_reprompts(self):
        ctx = make_context()
        ctx.user_data.update({
            "aims_settings": _ALL_SHOWN,
            "aims_calories": 2200,
            "aims_proteins": 150,
            "aims_fats": 70,
        })
        result = await receive_carbs(make_update(text="abc"), ctx)
        assert result == AIMS_CARBS

    async def test_out_of_range_reprompts(self):
        ctx = make_context()
        ctx.user_data.update({
            "aims_settings": _ALL_SHOWN,
            "aims_calories": 2200,
            "aims_proteins": 150,
            "aims_fats": 70,
        })
        result = await receive_carbs(make_update(text="5000"), ctx)
        assert result == AIMS_CARBS


# ---------------------------------------------------------------------------
# Skipping disabled fields
# ---------------------------------------------------------------------------

class TestSkipDisabledFields:
    async def test_only_calories_saves_after_one_input(self):
        """When only calories is enabled, entering it should save and end."""
        ctx = make_context()
        ctx.user_data["aims_settings"] = _ONLY_CALORIES
        update = make_update(text="2000")

        with patch("handlers.aims.database.save_user_aims", new_callable=AsyncMock) as save:
            result = await receive_calories(update, ctx)

        assert result == ConversationHandler.END
        save.assert_awaited_once_with(
            user_id=1,
            target_calories=2000,
            target_proteins=0,
            target_fats=0,
            target_carbs=0,
        )

    async def test_skips_disabled_mid_flow(self):
        """Proteins disabled: after calories, should jump to fats."""
        settings = {**_ALL_SHOWN, "show_proteins": False}
        ctx = make_context()
        ctx.user_data["aims_settings"] = settings
        result = await receive_calories(make_update(text="2000"), ctx)
        assert result == AIMS_FATS


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestCancelAims:
    async def test_cancel_ends_conversation(self):
        ctx = make_context()
        ctx.user_data["aims_calories"] = 2200
        ctx.user_data["aims_settings"] = _ALL_SHOWN
        update = make_update()
        result = await cancel_aims(update, ctx)
        assert result == ConversationHandler.END
        assert "aims_calories" not in ctx.user_data
        assert "aims_settings" not in ctx.user_data
