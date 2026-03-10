"""
Telegram handlers for food-related messages and commands.

These are thin coordinators: they delegate to services and format replies.
No business logic lives here — that belongs in services/claude.py and
services/database.py.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from services import claude, database
from utils.photos import photo_to_base64

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 500


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a text food description or a reply to a clarifying question.

    Delegates to claude.estimate_from_text. If Claude needs more info it
    replies with a question and returns (preserving conversation state).
    Otherwise logs the meal and confirms to the user.
    """
    user_id = update.effective_user.id
    text = update.message.text
    logger.info("Text from user %d: %s", user_id, text)

    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(
            f"Message too long — please keep it under {MAX_TEXT_LENGTH} characters."
        )
        return

    await update.message.reply_text("⏳ Estimating calories...")

    estimate = await claude.estimate_from_text(user_id, text)

    if estimate.clarifying_question:
        await update.message.reply_text(estimate.clarifying_question)
        return

    await database.log_meal(
        user_id=user_id,
        description=", ".join(estimate.food_items) or text,
        calories=estimate.calories_estimate,
        input_type="text",
    )
    claude.clear_conversation(user_id)

    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)} — "
        f"~{estimate.calories_estimate} kcal "
        f"(confidence: {estimate.confidence:.0%})"
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a food photo, optionally with a caption.

    Downloads the highest-resolution photo, base64-encodes it, and sends
    it to Claude vision. Same clarifying loop as handle_text.
    """
    user_id = update.effective_user.id
    logger.info("Photo from user %d", user_id)

    await update.message.reply_text("📸 Analysing your photo...")

    photo = update.message.photo[-1]  # highest resolution
    image_b64 = await photo_to_base64(photo, context.bot)
    caption = update.message.caption

    estimate = await claude.estimate_from_photo(user_id, image_b64, caption)

    if estimate.clarifying_question:
        await update.message.reply_text(estimate.clarifying_question)
        return

    await database.log_meal(
        user_id=user_id,
        description=", ".join(estimate.food_items) or "photo",
        calories=estimate.calories_estimate,
        input_type="photo",
    )
    claude.clear_conversation(user_id)

    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)} — "
        f"~{estimate.calories_estimate} kcal "
        f"(confidence: {estimate.confidence:.0%})"
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with today's calorie total and meal list."""
    user_id = update.effective_user.id
    meals = await database.get_today(user_id)

    if not meals:
        await update.message.reply_text("📊 Nothing logged today yet.")
        return

    total = sum(m["calories"] for m in meals)
    lines = [f"• {m['description']} — {m['calories']} kcal" for m in meals]
    await update.message.reply_text(
        "📊 *Today's log:*\n\n" + "\n".join(lines) + f"\n\n*Total: {total} kcal*",
        parse_mode="Markdown",
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with a 7-day calorie summary grouped by date."""
    user_id = update.effective_user.id
    meals = await database.get_history(user_id, days=7)

    if not meals:
        await update.message.reply_text("📅 No meals logged in the last 7 days.")
        return

    # Group by date (first 10 chars of ISO timestamp)
    by_date: dict[str, int] = {}
    for m in meals:
        date = m["timestamp"][:10]
        by_date[date] = by_date.get(date, 0) + m["calories"]

    lines = [f"• {date}: {kcal} kcal" for date, kcal in sorted(by_date.items())]
    await update.message.reply_text(
        "📅 *Last 7 days:*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )
