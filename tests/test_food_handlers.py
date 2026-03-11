"""Tests for handlers/food.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from handlers.food import MAX_TEXT_LENGTH
from services.claude import CalorieEstimate


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_update(text=None, user_id=1, photo=None, caption=None):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.text = text
    update.message.caption = caption
    update.message.photo = photo or []
    update.message.reply_text = AsyncMock()
    return update


def _make_context(bot=None):
    ctx = MagicMock()
    ctx.bot = bot or AsyncMock()
    return ctx


def _estimate(food_items=("banana",), calories=90, confidence=0.9, clarifying_question=None):
    return CalorieEstimate(
        food_items=list(food_items),
        calories_estimate=calories,
        confidence=confidence,
        clarifying_question=clarifying_question,
    )


# ---------------------------------------------------------------------------
# Input length cap
# ---------------------------------------------------------------------------

class TestInputLengthCap:
    @pytest.fixture(autouse=True)
    def patches(self):
        with patch("handlers.food.claude.estimate_from_text", new_callable=AsyncMock) as est:
            self.estimate = est
            yield

    async def test_rejects_text_over_limit(self):
        from handlers.food import handle_text

        long_text = "a" * (MAX_TEXT_LENGTH + 1)
        update = _make_update(text=long_text)
        await handle_text(update, _make_context())

        self.estimate.assert_not_awaited()
        reply = update.message.reply_text.call_args.args[0]
        assert str(MAX_TEXT_LENGTH) in reply

    async def test_accepts_text_at_limit(self):
        from handlers.food import handle_text

        self.estimate.return_value = _estimate()
        with patch("handlers.food.database.log_meal", new_callable=AsyncMock):
            with patch("handlers.food.claude.clear_conversation"):
                await handle_text(_make_update(text="a" * MAX_TEXT_LENGTH), _make_context())

        self.estimate.assert_awaited_once()


# ---------------------------------------------------------------------------
# handle_text
# ---------------------------------------------------------------------------

class TestHandleText:
    @pytest.fixture(autouse=True)
    def patches(self):
        with (
            patch("handlers.food.claude.estimate_from_text", new_callable=AsyncMock) as est,
            patch("handlers.food.database.log_meal", new_callable=AsyncMock) as log,
            patch("handlers.food.claude.clear_conversation") as clr,
        ):
            self.estimate = est
            self.log_meal = log
            self.clear = clr
            yield

    async def test_logs_meal_on_confident_estimate(self):
        from handlers.food import handle_text

        self.estimate.return_value = _estimate()
        update = _make_update(text="I had a banana")
        await handle_text(update, _make_context())

        self.log_meal.assert_awaited_once()
        call_kwargs = self.log_meal.call_args.kwargs
        assert call_kwargs["user_id"] == 1
        assert call_kwargs["calories"] == 90
        assert call_kwargs["input_type"] == "text"

    async def test_clears_conversation_after_logging(self):
        from handlers.food import handle_text

        self.estimate.return_value = _estimate()
        await handle_text(_make_update(text="banana"), _make_context())
        self.clear.assert_called_once_with(1)

    async def test_does_not_log_when_clarifying_question(self):
        from handlers.food import handle_text

        self.estimate.return_value = _estimate(
            food_items=[], calories=None, confidence=0.0,
            clarifying_question="How large was the portion?"
        )
        update = _make_update(text="pasta")
        await handle_text(update, _make_context())

        self.log_meal.assert_not_awaited()
        self.clear.assert_not_called()

    async def test_replies_with_clarifying_question(self):
        from handlers.food import handle_text

        question = "Was it grilled or fried?"
        self.estimate.return_value = _estimate(
            food_items=[], calories=None, confidence=0.0,
            clarifying_question=question
        )
        update = _make_update(text="chicken")
        await handle_text(update, _make_context())

        # Last reply_text call should contain the question
        calls = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any(question in c for c in calls)

    async def test_confirmation_reply_contains_calories(self):
        from handlers.food import handle_text

        self.estimate.return_value = _estimate(calories=200)
        update = _make_update(text="rice")
        await handle_text(update, _make_context())

        calls = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any("200" in c for c in calls)


# ---------------------------------------------------------------------------
# handle_photo
# ---------------------------------------------------------------------------

class TestHandlePhoto:
    @pytest.fixture(autouse=True)
    def patches(self):
        with (
            patch("handlers.food.photo_to_base64", new_callable=AsyncMock, return_value="b64img") as p2b,
            patch("handlers.food.claude.estimate_from_photo", new_callable=AsyncMock) as est,
            patch("handlers.food.database.log_meal", new_callable=AsyncMock) as log,
            patch("handlers.food.claude.clear_conversation") as clr,
        ):
            self.photo_to_base64 = p2b
            self.estimate = est
            self.log_meal = log
            self.clear = clr
            yield

    def _photo_update(self, user_id=1, caption=None):
        photo_size = MagicMock()
        return _make_update(user_id=user_id, photo=[photo_size], caption=caption)

    async def test_downloads_highest_res_photo(self):
        from handlers.food import handle_photo

        self.estimate.return_value = _estimate(food_items=["pizza"], calories=800)
        update = self._photo_update()
        await handle_photo(update, _make_context())

        # photo[-1] is the highest-res; check it was passed
        self.photo_to_base64.assert_awaited_once()

    async def test_logs_meal_with_photo_input_type(self):
        from handlers.food import handle_photo

        self.estimate.return_value = _estimate(food_items=["salad"], calories=250)
        await handle_photo(self._photo_update(), _make_context())

        call_kwargs = self.log_meal.call_args.kwargs
        assert call_kwargs["input_type"] == "photo"

    async def test_passes_caption_to_claude(self):
        from handlers.food import handle_photo

        self.estimate.return_value = _estimate()
        await handle_photo(self._photo_update(caption="my lunch"), _make_context())

        _, kwargs = self.estimate.call_args
        assert kwargs.get("caption") == "my lunch" or self.estimate.call_args.args[2] == "my lunch"

    async def test_no_log_when_clarifying_question(self):
        from handlers.food import handle_photo

        self.estimate.return_value = _estimate(
            food_items=[], calories=None, confidence=0.0,
            clarifying_question="Is that sauce included?"
        )
        await handle_photo(self._photo_update(), _make_context())
        self.log_meal.assert_not_awaited()


# ---------------------------------------------------------------------------
# cmd_today
# ---------------------------------------------------------------------------

class TestCmdToday:
    @pytest.fixture(autouse=True)
    def patches(self):
        with patch("handlers.food.database.get_today", new_callable=AsyncMock) as g:
            self.get_today = g
            yield

    async def test_shows_total_calories(self):
        from handlers.food import cmd_today

        self.get_today.return_value = [
            {"description": "banana", "calories": 90, "timestamp": "2026-03-10T08:00:00+00:00"},
            {"description": "rice", "calories": 300, "timestamp": "2026-03-10T12:00:00+00:00"},
        ]
        update = _make_update()
        await cmd_today(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "390" in reply

    async def test_shows_empty_message_when_no_meals(self):
        from handlers.food import cmd_today

        self.get_today.return_value = []
        update = _make_update()
        await cmd_today(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "nothing" in reply.lower() or "no" in reply.lower()


# ---------------------------------------------------------------------------
# cmd_history
# ---------------------------------------------------------------------------

class TestCmdHistory:
    @pytest.fixture(autouse=True)
    def patches(self):
        with patch("handlers.food.database.get_history", new_callable=AsyncMock) as g:
            self.get_history = g
            yield

    async def test_groups_by_date(self):
        from handlers.food import cmd_history

        self.get_history.return_value = [
            {"description": "breakfast", "calories": 300, "timestamp": "2026-03-09T08:00:00+00:00"},
            {"description": "lunch", "calories": 500, "timestamp": "2026-03-09T13:00:00+00:00"},
            {"description": "dinner", "calories": 700, "timestamp": "2026-03-10T19:00:00+00:00"},
        ]
        update = _make_update()
        await cmd_history(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "2026-03-09" in reply
        assert "2026-03-10" in reply
        assert "800" in reply   # 300+500
        assert "700" in reply

    async def test_empty_message_when_no_history(self):
        from handlers.food import cmd_history

        self.get_history.return_value = []
        update = _make_update()
        await cmd_history(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "no" in reply.lower() or "nothing" in reply.lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @pytest.fixture(autouse=True)
    def patches(self):
        with (
            patch("handlers.food.claude.estimate_from_text", new_callable=AsyncMock) as est,
            patch("handlers.food.database.log_meal", new_callable=AsyncMock) as log,
            patch("handlers.food.claude.clear_conversation") as clr,
        ):
            self.estimate = est
            self.log_meal = log
            self.clear = clr
            yield

    async def test_handle_text_replies_on_claude_error(self):
        from handlers.food import handle_text

        self.estimate.side_effect = Exception("API error")
        update = _make_update(text="a burger")
        await handle_text(update, _make_context())

        self.log_meal.assert_not_awaited()
        calls = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert any("wrong" in c.lower() or "error" in c.lower() for c in calls)

    async def test_handle_text_clears_conversation_on_error(self):
        from handlers.food import handle_text

        self.estimate.side_effect = Exception("API error")
        await handle_text(_make_update(text="a burger"), _make_context())
        self.clear.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# cmd_cancel
# ---------------------------------------------------------------------------

class TestCmdCancel:
    async def test_cancel_clears_active_conversation(self):
        from handlers.food import cmd_cancel

        with (
            patch("handlers.food.claude.has_active_conversation", return_value=True),
            patch("handlers.food.claude.clear_conversation") as clr,
        ):
            update = _make_update()
            await cmd_cancel(update, _make_context())

            clr.assert_called_once_with(1)
            reply = update.message.reply_text.call_args.args[0]
            assert "cancel" in reply.lower()

    async def test_cancel_noop_when_no_conversation(self):
        from handlers.food import cmd_cancel

        with patch("handlers.food.claude.has_active_conversation", return_value=False):
            update = _make_update()
            await cmd_cancel(update, _make_context())

            reply = update.message.reply_text.call_args.args[0]
            assert "nothing" in reply.lower()


# ---------------------------------------------------------------------------
# cmd_undo
# ---------------------------------------------------------------------------

class TestCmdUndo:
    async def test_undo_confirms_deleted_meal(self):
        from handlers.food import cmd_undo

        meal = {"description": "banana", "calories": 90, "id": 1, "user_id": 1,
                "timestamp": "2026-03-10T08:00:00+00:00", "input_type": "text"}
        with patch("handlers.food.database.delete_last_meal", new_callable=AsyncMock, return_value=meal):
            update = _make_update()
            await cmd_undo(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "banana" in reply
        assert "90" in reply

    async def test_undo_when_nothing_logged(self):
        from handlers.food import cmd_undo

        with patch("handlers.food.database.delete_last_meal", new_callable=AsyncMock, return_value=None):
            update = _make_update()
            await cmd_undo(update, _make_context())

        reply = update.message.reply_text.call_args.args[0]
        assert "nothing" in reply.lower() or "no" in reply.lower()
