"""
Calorie Tracker Bot — main entry point.

Wires up handlers and starts polling. Business logic lives in handlers/ and services/.
"""

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from handlers.food import handle_text, handle_photo, cmd_today, cmd_history
from services.database import init_db

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
# Inline commands (no external dependencies)
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message."""
    await update.message.reply_text(
        "👋 Hi! I'm your personal calorie tracker.\n\n"
        "Just send me:\n"
        "• 📸 A photo of your food\n"
        "• ✍️ A text description of what you ate\n\n"
        "I'll estimate the calories and log them for you.\n\n"
        "Commands:\n"
        "/today — see today's total\n"
        "/history — last 7 days\n"
        "/help — show this message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

async def post_init(application: Application) -> None:
    await init_db()
    logger.info("Database initialised.")


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

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & allowed, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO & allowed, handle_photo))

    logger.info("Bot is running... (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
