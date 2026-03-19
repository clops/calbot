"""Shared test fixtures for handler tests."""

from unittest.mock import AsyncMock, MagicMock


def make_update(text=None, user_id=1, photo=None, caption=None):
    """Build a mock Telegram Update."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.language_code = "en"
    update.message.text = text
    update.message.caption = caption
    update.message.photo = photo or []
    update.message.reply_text = AsyncMock()
    return update


def make_context(bot=None, user_data=None):
    """Build a mock CallbackContext."""
    ctx = MagicMock()
    ctx.bot = bot or AsyncMock()
    ctx.user_data = user_data if user_data is not None else {}
    return ctx


def make_callback_update(data, user_id=1):
    """Build a mock Update with a callback query."""
    query = AsyncMock()
    query.data = data
    query.from_user.id = user_id
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    return update
