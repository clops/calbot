"""
Calorie Tracker Bot — main entry point.

Wires up handlers and starts polling. Business logic lives in handlers/ and services/.
"""

import datetime
import logging
import os

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from handlers.food import handle_text, handle_photo, cmd_today, cmd_history, cmd_cancel, cmd_undo, cmd_settings, settings_callback
from handlers.profile import build_profile_conversation
from services import claude, database
from services.database import init_db
from utils.i18n import t

def _build_allowlist() -> filters.BaseFilter:
    """Return a user filter from ALLOWED_USER_IDS env var, or allow all if unset."""
    raw = os.getenv("ALLOWED_USER_IDS", "").strip()
    if not raw:
        logger.warning("ALLOWED_USER_IDS is not set — bot is open to all users")
        return filters.ALL
    ids = [int(uid.strip()) for uid in raw.split(",") if uid.strip()]
    logger.info("Allowlist active: %s", ids)
    return filters.User(user_id=ids)

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Keyboard button labels across all supported languages
# ---------------------------------------------------------------------------

_ALL_TODAY_LABELS = [t("btn_today", lang) for lang in ("en", "de", "ru")]
_ALL_HISTORY_LABELS = [t("btn_history", lang) for lang in ("en", "de", "ru")]
_ALL_BUTTON_LABELS = _ALL_TODAY_LABELS + _ALL_HISTORY_LABELS


def _build_keyboard(lang: str | None = None) -> ReplyKeyboardMarkup:
    """Build a persistent keyboard in the user's language."""
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t("btn_today", lang)), KeyboardButton(t("btn_history", lang))]],
        resize_keyboard=True,
        is_persistent=True,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    lang = update.effective_user.language_code if update.effective_user else None
    await update.message.reply_text(
        t("welcome", lang),
        reply_markup=_build_keyboard(lang),
    )


async def handle_keyboard_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route persistent keyboard button taps to their command handlers."""
    text = update.message.text
    if text in _ALL_TODAY_LABELS:
        await cmd_today(update, context)
    elif text in _ALL_HISTORY_LABELS:
        await cmd_history(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


# ---------------------------------------------------------------------------
# Daily reminder job
# ---------------------------------------------------------------------------

async def _send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check each reminder-enabled user and nudge them if they haven't logged today."""
    users = await database.get_reminder_users()
    for user in users:
        user_id = user["user_id"]
        try:
            meals = await database.get_today(user_id)
            if meals:
                continue
            nudge = await claude.generate_nudge(user["language_code"])
            await context.bot.send_message(chat_id=user_id, text=nudge)
            logger.info("Sent daily nudge to user %d", user_id)
        except Exception:
            logger.exception("Failed to send nudge to user %d", user_id)


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    await init_db()
    logger.info("Database initialised.")

    # Schedule daily reminder at 20:00 CET
    cet = datetime.timezone(datetime.timedelta(hours=1))
    application.job_queue.run_daily(
        _send_daily_reminders,
        time=datetime.time(hour=20, minute=0, tzinfo=cet),
        name="daily_reminder",
    )
    logger.info("Daily reminder job scheduled for 20:00 CET.")


def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    allowed = _build_allowlist()

    # Commands
    app.add_handler(CommandHandler("start",   cmd_start,   filters=allowed))
    app.add_handler(CommandHandler("help",    cmd_help,    filters=allowed))
    app.add_handler(CommandHandler("today",   cmd_today,   filters=allowed))
    app.add_handler(CommandHandler("history", cmd_history, filters=allowed))
    app.add_handler(CommandHandler("cancel",  cmd_cancel,  filters=allowed))
    app.add_handler(CommandHandler("undo",    cmd_undo,    filters=allowed))
    app.add_handler(CommandHandler("settings", cmd_settings, filters=allowed))
    app.add_handler(CallbackQueryHandler(settings_callback, pattern="^toggle:"))

    # Profile conversation (must be before general text handler)
    app.add_handler(build_profile_conversation(allowed))

    # Keyboard buttons (must be before the general text handler)
    button_filter = filters.Text(_ALL_BUTTON_LABELS) & allowed
    app.add_handler(MessageHandler(button_filter, handle_keyboard_buttons))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Text(_ALL_BUTTON_LABELS) & allowed, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & allowed, handle_photo))

    logger.info("Bot is running... (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
