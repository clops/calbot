"""Shared utility helpers for handlers."""

from telegram import Update

from services import database


def get_user_lang(update: Update) -> str | None:
    """Extract the user's Telegram language_code from an Update."""
    if update.effective_user:
        return update.effective_user.language_code
    return None


async def resolve_language(update: Update) -> str | None:
    """Return the effective language for a user.

    If the user has manually picked a language, return that.
    Otherwise fall back to Telegram's language_code and persist it.
    """
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return get_user_lang(update)

    settings = await database.get_user_settings(user_id)
    if settings.get("language_manual"):
        return settings.get("language_code")

    lang = get_user_lang(update)
    if lang:
        await database.update_language(user_id, lang)
    return lang
