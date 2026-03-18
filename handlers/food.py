"""
Telegram handlers for food-related messages and commands.

These are thin coordinators: they delegate to services and format replies.
No business logic lives here — that belongs in services/claude.py and
services/database.py.
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services import claude, database
from utils.photos import photo_to_base64

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 500

_SETTING_LABELS = {
    "show_calories": "Calories",
    "show_proteins": "Proteins",
    "show_fats": "Fats",
    "show_carbohydrates": "Carbs",
}


def _format_nutrition(calories, proteins, fats, carbs, settings=None):
    """Build a nutrition string respecting user display settings."""
    if settings is None:
        settings = {k: True for k in _SETTING_LABELS}
    parts = []
    if settings.get("show_calories", True):
        parts.append(f"~{calories} kcal")
    if proteins is not None:
        if settings.get("show_proteins", True):
            parts.append(f"P: {proteins}g")
        if settings.get("show_fats", True):
            parts.append(f"F: {fats}g")
        if settings.get("show_carbohydrates", True):
            parts.append(f"C: {carbs}g")
    if not parts:
        return ""
    # Separate calories from macros with a pipe
    cal_part = []
    macro_parts = []
    for p in parts:
        if "kcal" in p:
            cal_part.append(p)
        else:
            macro_parts.append(p)
    if cal_part and macro_parts:
        return cal_part[0] + " | " + "  ".join(macro_parts)
    return "  ".join(parts) if not cal_part else cal_part[0]


def _settings_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Build an inline keyboard showing current toggle states."""
    buttons = []
    for field, label in _SETTING_LABELS.items():
        icon = "✅" if settings.get(field) else "❌"
        buttons.append([InlineKeyboardButton(f"{label}: {icon}", callback_data=f"toggle:{field}")])
    return InlineKeyboardMarkup(buttons)


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

    settings = await database.get_user_settings(user_id)
    nutrition = _format_nutrition(
        estimate.calories_estimate, estimate.proteins_g,
        estimate.fats_g, estimate.carbohydrates_g, settings,
    )
    suffix = f" — {nutrition}" if nutrition else ""
    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)}{suffix}"
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

    settings = await database.get_user_settings(user_id)
    nutrition = _format_nutrition(
        estimate.calories_estimate, estimate.proteins_g,
        estimate.fats_g, estimate.carbohydrates_g, settings,
    )
    suffix = f" — {nutrition}" if nutrition else ""
    await update.message.reply_text(
        f"✅ Logged! {', '.join(estimate.food_items)}{suffix}"
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

    settings = await database.get_user_settings(user_id)

    meal_lines = []
    for m in meals:
        nutrition = _format_nutrition(
            m["calories"], m.get("proteins"), m.get("fats"),
            m.get("carbohydrates"), settings,
        )
        suffix = f" — {nutrition}" if nutrition else ""
        meal_lines.append(f"• {m['description']}{suffix}")

    total_cal = sum(m["calories"] for m in meals)
    total_nutrition = _format_nutrition(
        total_cal,
        sum(m.get("proteins") or 0 for m in meals) if any(m.get("proteins") is not None for m in meals) else None,
        sum(m.get("fats") or 0 for m in meals) if any(m.get("proteins") is not None for m in meals) else None,
        sum(m.get("carbohydrates") or 0 for m in meals) if any(m.get("proteins") is not None for m in meals) else None,
        settings,
    )
    footer = f"*Total: {total_nutrition}*" if total_nutrition else f"*Total: {total_cal} kcal*"

    await update.message.reply_text(
        "📊 *Today's log:*\n\n" + "\n".join(meal_lines) + f"\n\n{footer}",
        parse_mode="Markdown",
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with a 7-day calorie summary grouped by date."""
    user_id = update.effective_user.id
    meals = await database.get_history(user_id, days=7)

    if not meals:
        await update.message.reply_text("📅 No meals logged in the last 7 days.")
        return

    settings = await database.get_user_settings(user_id)

    # Group by date (first 10 chars of ISO timestamp)
    by_date: dict[str, dict] = {}
    for m in meals:
        date = m["timestamp"][:10]
        if date not in by_date:
            by_date[date] = {"calories": 0, "proteins": 0, "fats": 0, "carbohydrates": 0, "has_macros": False}
        by_date[date]["calories"] += m["calories"]
        if m.get("proteins") is not None:
            by_date[date]["has_macros"] = True
            by_date[date]["proteins"] += m.get("proteins") or 0
            by_date[date]["fats"] += m.get("fats") or 0
            by_date[date]["carbohydrates"] += m.get("carbohydrates") or 0

    lines = []
    for date, totals in sorted(by_date.items()):
        p = totals["proteins"] if totals["has_macros"] else None
        f_ = totals["fats"] if totals["has_macros"] else None
        c = totals["carbohydrates"] if totals["has_macros"] else None
        nutrition = _format_nutrition(totals["calories"], p, f_, c, settings)
        lines.append(f"• {date}: {nutrition}" if nutrition else f"• {date}: {totals['calories']} kcal")

    await update.message.reply_text(
        "📅 *Last 7 days:*\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show display settings with toggle buttons."""
    user_id = update.effective_user.id
    settings = await database.get_user_settings(user_id)
    await update.message.reply_text(
        "⚙️ *Display settings*\nChoose which nutrition info to show:",
        parse_mode="Markdown",
        reply_markup=_settings_keyboard(settings),
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard toggle presses for settings."""
    query = update.callback_query
    await query.answer()

    field = query.data.removeprefix("toggle:")
    user_id = query.from_user.id

    try:
        await database.toggle_setting(user_id, field)
    except ValueError:
        return

    settings = await database.get_user_settings(user_id)
    await query.edit_message_text(
        "⚙️ *Display settings*\nChoose which nutrition info to show:",
        parse_mode="Markdown",
        reply_markup=_settings_keyboard(settings),
    )
