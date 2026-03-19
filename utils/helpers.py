"""Shared utility helpers for handlers."""

from telegram import Update


def get_user_lang(update: Update) -> str | None:
    """Extract the user's Telegram language_code from an Update."""
    if update.effective_user:
        return update.effective_user.language_code
    return None
