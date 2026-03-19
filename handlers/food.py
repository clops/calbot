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
from utils.i18n import t
from utils.photos import photo_to_base64

logger = logging.getLogger(__name__)

MAX_TEXT_LENGTH = 500

_SETTING_LABELS = {
    "show_calories": "label_calories",
    "show_proteins": "label_proteins",
    "show_fats": "label_fats",
    "show_carbohydrates": "label_carbs",
    "show_reminders": "label_reminders",
}


def _lang(update: Update) -> str | None:
    """Extract the user's Telegram language_code."""
    if update.effective_user:
        return update.effective_user.language_code
    return None


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


def _settings_keyboard(settings: dict, lang: str | None = None) -> InlineKeyboardMarkup:
    """Build an inline keyboard showing current toggle states."""
    buttons = []
    for field, label_key in _SETTING_LABELS.items():
        icon = "✅" if settings.get(field) else "❌"
        label = t(label_key, lang)
        buttons.append([InlineKeyboardButton(f"{label}: {icon}", callback_data=f"toggle:{field}")])
    return InlineKeyboardMarkup(buttons)


def _format_totals_with_targets(total_cal, total_p, total_f, total_c, profile, settings, lang=None):
    """Build a footer string showing progress toward daily targets."""
    parts = []
    if settings.get("show_calories", True):
        tc = profile["target_calories"]
        pct = round(total_cal / tc * 100) if tc else 0
        parts.append(f"~{total_cal}/{tc} kcal ({pct}%)")

    macro_parts = []
    if total_p is not None:
        if settings.get("show_proteins", True):
            macro_parts.append(f"P: {total_p}/{profile['target_proteins']}g")
        if settings.get("show_fats", True):
            macro_parts.append(f"F: {total_f}/{profile['target_fats']}g")
        if settings.get("show_carbohydrates", True):
            macro_parts.append(f"C: {total_c}/{profile['target_carbs']}g")

    if not parts and not macro_parts:
        return ""
    lines = []
    if parts:
        lines.append(f"*{t('total', lang)}: {parts[0]}*")
    if macro_parts:
        lines.append(f"*{'  '.join(macro_parts)}*")
    return "\n".join(lines)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a text food description or a reply to a clarifying question."""
    user_id = update.effective_user.id
    text = update.message.text
    lang = _lang(update)
    if lang:
        await database.update_language(user_id, lang)
    logger.info("Text from user %d: %s", user_id, text)

    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(t("msg_too_long", lang, limit=MAX_TEXT_LENGTH))
        return

    await update.message.reply_text(t("estimating", lang))

    try:
        estimate = await claude.estimate_from_text(user_id, text, language_code=lang)
    except Exception:
        logger.exception("Claude call failed for user %d", user_id)
        claude.clear_conversation(user_id)
        await update.message.reply_text(t("error", lang))
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
    items = ", ".join(estimate.food_items)
    await update.message.reply_text(t("logged", lang, items=items, suffix=suffix))


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a food photo, optionally with a caption."""
    user_id = update.effective_user.id
    lang = _lang(update)
    if lang:
        await database.update_language(user_id, lang)
    logger.info("Photo from user %d", user_id)

    await update.message.reply_text(t("analysing_photo", lang))

    photo = update.message.photo[-1]  # highest resolution
    image_b64 = await photo_to_base64(photo, context.bot)
    caption = update.message.caption

    try:
        estimate = await claude.estimate_from_photo(user_id, image_b64, caption, language_code=lang)
    except Exception:
        logger.exception("Claude call failed for user %d", user_id)
        claude.clear_conversation(user_id)
        await update.message.reply_text(t("error", lang))
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
    items = ", ".join(estimate.food_items)
    await update.message.reply_text(t("logged", lang, items=items, suffix=suffix))


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Abort any in-progress clarifying question exchange."""
    user_id = update.effective_user.id
    lang = _lang(update)
    if claude.has_active_conversation(user_id):
        claude.clear_conversation(user_id)
        await update.message.reply_text(t("cancelled", lang))
    else:
        await update.message.reply_text(t("nothing_to_cancel", lang))


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the last logged meal and confirm to the user."""
    user_id = update.effective_user.id
    lang = _lang(update)
    meal = await database.delete_last_meal(user_id)
    if meal is None:
        await update.message.reply_text(t("nothing_to_undo", lang))
        return
    await update.message.reply_text(
        t("undo_done", lang, desc=meal["description"], cal=meal["calories"])
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with today's calorie total and meal list."""
    user_id = update.effective_user.id
    lang = _lang(update)
    meals = await database.get_today(user_id)

    if not meals:
        await update.message.reply_text(t("nothing_today", lang))
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
    has_macros = any(m.get("proteins") is not None for m in meals)
    total_p = sum(m.get("proteins") or 0 for m in meals) if has_macros else None
    total_f = sum(m.get("fats") or 0 for m in meals) if has_macros else None
    total_c = sum(m.get("carbohydrates") or 0 for m in meals) if has_macros else None

    profile = await database.get_user_profile(user_id)
    if profile:
        footer = _format_totals_with_targets(total_cal, total_p, total_f, total_c, profile, settings, lang)
    else:
        total_nutrition = _format_nutrition(total_cal, total_p, total_f, total_c, settings)
        footer = f"*{t('total', lang)}: {total_nutrition}*" if total_nutrition else f"*{t('total', lang)}: {total_cal} kcal*"

    await update.message.reply_text(
        t("today_header", lang) + "\n\n" + "\n".join(meal_lines) + f"\n\n{footer}",
        parse_mode="Markdown",
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with a 7-day calorie summary grouped by date."""
    user_id = update.effective_user.id
    lang = _lang(update)
    meals = await database.get_history(user_id, days=7)

    if not meals:
        await update.message.reply_text(t("no_history", lang))
        return

    settings = await database.get_user_settings(user_id)
    profile = await database.get_user_profile(user_id)

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
        cal = totals["calories"]
        p = totals["proteins"] if totals["has_macros"] else None
        f_ = totals["fats"] if totals["has_macros"] else None
        c = totals["carbohydrates"] if totals["has_macros"] else None

        if profile:
            tc = profile["target_calories"]
            pct = round(cal / tc * 100) if tc else 0
            icon = "✅" if 80 <= pct <= 120 else "⚠️" if pct > 120 else "❌"
            nutrition = _format_nutrition(cal, p, f_, c, settings)
            lines.append(f"{icon} {date}: {nutrition}" if nutrition else f"{icon} {date}")
        else:
            nutrition = _format_nutrition(cal, p, f_, c, settings)
            lines.append(f"• {date}: {nutrition}" if nutrition else f"• {date}: {cal} kcal")

    await update.message.reply_text(
        t("history_header", lang) + "\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show display settings with toggle buttons."""
    user_id = update.effective_user.id
    lang = _lang(update)
    settings = await database.get_user_settings(user_id)
    await update.message.reply_text(
        t("settings_header", lang),
        parse_mode="Markdown",
        reply_markup=_settings_keyboard(settings, lang),
    )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard toggle presses for settings."""
    query = update.callback_query
    await query.answer()

    field = query.data.removeprefix("toggle:")
    user_id = query.from_user.id
    lang = None
    if update.effective_user:
        lang = update.effective_user.language_code

    try:
        await database.toggle_setting(user_id, field)
    except ValueError:
        return

    settings = await database.get_user_settings(user_id)
    await query.edit_message_text(
        t("settings_header", lang),
        parse_mode="Markdown",
        reply_markup=_settings_keyboard(settings, lang),
    )
