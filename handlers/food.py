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

    try:
        estimate = await claude.estimate_from_text(user_id, text)
    except Exception:
        logger.exception("Claude call failed for user %d", user_id)
        claude.clear_conversation(user_id)
        await update.message.reply_text("Something went wrong — please try again.")
        return

    if estimate.clarifying_question:
        await update.message.reply_text(estimate.clarifying_question)
        return

    await database.log_meal(
        user_id=user_id,
        description=", ".join(estimate.food_items) or text,
        calories=estimate.calories_estimate,
        input_type="text",
        proteins=estimate.proteins_g,
        fats=estimate.fats_g,
        carbohydrates=estimate.carbohydrates_g,
    )
    claude.clear_conversation(user_id)

    macro_str = ""
    if estimate.proteins_g is not None:
        macro_str = f" | P: {estimate.proteins_g}g  F: {estimate.fats_g}g  C: {estimate.carbohydrates_g}g"
    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)} — "
        f"~{estimate.calories_estimate} kcal{macro_str} "
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

    try:
        estimate = await claude.estimate_from_photo(user_id, image_b64, caption)
    except Exception:
        logger.exception("Claude call failed for user %d", user_id)
        claude.clear_conversation(user_id)
        await update.message.reply_text("Something went wrong — please try again.")
        return

    if estimate.clarifying_question:
        await update.message.reply_text(estimate.clarifying_question)
        return

    await database.log_meal(
        user_id=user_id,
        description=", ".join(estimate.food_items) or "photo",
        calories=estimate.calories_estimate,
        input_type="photo",
        proteins=estimate.proteins_g,
        fats=estimate.fats_g,
        carbohydrates=estimate.carbohydrates_g,
    )
    claude.clear_conversation(user_id)

    macro_str = ""
    if estimate.proteins_g is not None:
        macro_str = f" | P: {estimate.proteins_g}g  F: {estimate.fats_g}g  C: {estimate.carbohydrates_g}g"
    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)} — "
        f"~{estimate.calories_estimate} kcal{macro_str} "
        f"(confidence: {estimate.confidence:.0%})"
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Abort any in-progress clarifying question exchange."""
    user_id = update.effective_user.id
    if claude.has_active_conversation(user_id):
        claude.clear_conversation(user_id)
        await update.message.reply_text("Cancelled. Send a new food description whenever you're ready.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the last logged meal and confirm to the user."""
    user_id = update.effective_user.id
    meal = await database.delete_last_meal(user_id)
    if meal is None:
        await update.message.reply_text("Nothing to undo — no meals logged yet.")
        return
    await update.message.reply_text(
        f"↩️ Removed: {meal['description']} — {meal['calories']} kcal"
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

    footer = f"*Total: {total} kcal*"
    if any(m.get("proteins") is not None for m in meals):
        p = sum(m.get("proteins") or 0 for m in meals)
        f_ = sum(m.get("fats") or 0 for m in meals)
        c = sum(m.get("carbohydrates") or 0 for m in meals)
        footer += f"  |  P: {p}g  F: {f_}g  C: {c}g"

    await update.message.reply_text(
        "📊 *Today's log:*\n\n" + "\n".join(lines) + f"\n\n{footer}",
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
