"""
Calorie Tracker Bot — main entry point
Phase 1: Foundation (hello world + command scaffold)
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

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Command handlers
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


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show today's calorie total. (Stub — Phase 3)"""
    await update.message.reply_text(
        "📊 Today's log coming in Phase 3! Stay tuned."
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show 7-day history. (Stub — Phase 3)"""
    await update.message.reply_text(
        "📅 History view coming in Phase 3! Stay tuned."
    )


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text descriptions of food. (Stub — Phase 2)"""
    user_text = update.message.text
    logger.info("Text from user %s: %s", update.effective_user.id, user_text)
    await update.message.reply_text(
        f"Got it! 🍽️ You said:\n\n_{user_text}_\n\n"
        "Calorie estimation coming in Phase 2!",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle food photos. (Stub — Phase 2)"""
    logger.info("Photo from user %s", update.effective_user.id)
    await update.message.reply_text(
        "📸 Got your photo! Calorie estimation from images coming in Phase 2!"
    )


# ---------------------------------------------------------------------------
# App bootstrap
# ---------------------------------------------------------------------------

def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set in .env")

    app = Application.builder().token(token).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("history", cmd_history))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Bot is running... (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
