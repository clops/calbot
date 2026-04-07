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
from utils.helpers import resolve_language
from utils.i18n import _normalise_lang, t
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

_LANGUAGE_OPTIONS = [("en", "English"), ("de", "Deutsch"), ("ru", "Русский")]


def _format_nutrition(calories, proteins, fats, carbs, settings=None, lang=None):
    """Build a nutrition string respecting user display settings."""
    if settings is None:
        settings = {k: True for k in _SETTING_LABELS}
    parts = []
    if settings.get("show_calories", True):
        parts.append(f"~{calories} kcal")
    if proteins is not None:
        lp, lf, lc = t("macro_p", lang), t("macro_f", lang), t("macro_c", lang)
        g = t("unit_g", lang)
        if settings.get("show_proteins", True):
            parts.append(f"{lp}: {proteins}{g}")
        if settings.get("show_fats", True):
            parts.append(f"{lf}: {fats}{g}")
        if settings.get("show_carbohydrates", True):
            parts.append(f"{lc}: {carbs}{g}")
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
    """Build an inline keyboard showing current toggle states and language picker."""
    buttons = []
    for field, label_key in _SETTING_LABELS.items():
        icon = "✅" if settings.get(field) else "❌"
        label = t(label_key, lang)
        buttons.append([InlineKeyboardButton(f"{label}: {icon}", callback_data=f"toggle:{field}")])

    # Language picker row
    current_lang = _normalise_lang(settings.get("language_code") or lang)
    lang_buttons = []
    for code, name in _LANGUAGE_OPTIONS:
        mark = " ✓" if code == current_lang else ""
        lang_buttons.append(InlineKeyboardButton(f"{name}{mark}", callback_data=f"lang:{code}"))
    buttons.append(lang_buttons)

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
        lp, lf, lc = t("macro_p", lang), t("macro_f", lang), t("macro_c", lang)
        g = t("unit_g", lang)
        if settings.get("show_proteins", True):
            macro_parts.append(f"{lp}: {total_p}/{profile['target_proteins']}{g}")
        if settings.get("show_fats", True):
            macro_parts.append(f"{lf}: {total_f}/{profile['target_fats']}{g}")
        if settings.get("show_carbohydrates", True):
            macro_parts.append(f"{lc}: {total_c}/{profile['target_carbs']}{g}")

    if not parts and not macro_parts:
        return ""
    lines = []
    if parts:
        lines.append(f"*{t('total', lang)}: {parts[0]}*")
    if macro_parts:
        lines.append(f"*{'  '.join(macro_parts)}*")
    return "\n".join(lines)


def _sum_macros(meals: list[dict]) -> tuple[int, int | None, int | None, int | None]:
    """Sum calories and macros from a list of meal dicts.

    Returns (total_cal, total_proteins, total_fats, total_carbs).
    Macro totals are None when no meal has macro data.
    """
    total_cal = sum(m["calories"] for m in meals)
    has_macros = any(m.get("proteins") is not None for m in meals)
    total_p = sum(m.get("proteins") or 0 for m in meals) if has_macros else None
    total_f = sum(m.get("fats") or 0 for m in meals) if has_macros else None
    total_c = sum(m.get("carbohydrates") or 0 for m in meals) if has_macros else None
    return total_cal, total_p, total_f, total_c


async def _process_estimate(update, user_id, estimate, input_type, fallback_desc, lang):
    """Shared post-estimation logic for text and photo handlers."""
    if estimate.clarifying_question:
        await update.message.reply_text(estimate.clarifying_question)
        return

    await database.log_meal(
        user_id=user_id,
        description=", ".join(estimate.food_items) or fallback_desc,
        calories=estimate.calories_estimate,
        input_type=input_type,
        proteins=estimate.proteins_g,
        fats=estimate.fats_g,
        carbohydrates=estimate.carbohydrates_g,
    )
    claude.clear_conversation(user_id)

    settings = await database.get_user_settings(user_id)
    nutrition = _format_nutrition(
        estimate.calories_estimate, estimate.proteins_g,
        estimate.fats_g, estimate.carbohydrates_g, settings, lang,
    )
    suffix = f" — {nutrition}" if nutrition else ""
    items = ", ".join(estimate.food_items)
    await update.message.reply_text(t("logged", lang, items=items, suffix=suffix))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a text food description or a reply to a clarifying question."""
    user_id = update.effective_user.id
    text = update.message.text
    lang = await resolve_language(update)
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

    await _process_estimate(update, user_id, estimate, "text", text, lang)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a food photo, optionally with a caption."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
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

    await _process_estimate(update, user_id, estimate, "photo", "photo", lang)


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Abort any in-progress clarifying question exchange."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
    if claude.has_active_conversation(user_id):
        claude.clear_conversation(user_id)
        await update.message.reply_text(t("cancelled", lang))
    else:
        await update.message.reply_text(t("nothing_to_cancel", lang))


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete the last logged meal and confirm to the user."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
    meal = await database.delete_last_meal(user_id)
    if meal is None:
        await update.message.reply_text(t("nothing_to_undo", lang))
        return
    settings = await database.get_user_settings(user_id)
    nutrition = _format_nutrition(
        meal["calories"], meal.get("proteins"),
        meal.get("fats"), meal.get("carbohydrates"), settings, lang,
    )
    suffix = f" — {nutrition}" if nutrition else ""
    await update.message.reply_text(
        t("undo_done", lang, desc=meal["description"], suffix=suffix)
    )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with today's calorie total and meal list."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
    meals = await database.get_today(user_id)

    if not meals:
        await update.message.reply_text(t("nothing_today", lang))
        return

    settings = await database.get_user_settings(user_id)

    meal_lines = []
    for m in meals:
        nutrition = _format_nutrition(
            m["calories"], m.get("proteins"), m.get("fats"),
            m.get("carbohydrates"), settings, lang,
        )
        line = f"• {m['description']}"
        if nutrition:
            line += f"\n    {nutrition}"
        meal_lines.append(line)

    total_cal, total_p, total_f, total_c = _sum_macros(meals)

    profile = await database.get_user_profile(user_id)
    if profile:
        footer = _format_totals_with_targets(total_cal, total_p, total_f, total_c, profile, settings, lang)
    else:
        total_nutrition = _format_nutrition(total_cal, total_p, total_f, total_c, settings, lang)
        footer = f"*{t('total', lang)}: {total_nutrition}*" if total_nutrition else f"*{t('total', lang)}: {total_cal} kcal*"

    await update.message.reply_text(
        t("today_header", lang) + "\n\n" + "\n".join(meal_lines) + f"\n\n{footer}",
        parse_mode="Markdown",
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply with a 7-day calorie summary grouped by date."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
    meals = await database.get_history(user_id, days=7)

    if not meals:
        await update.message.reply_text(t("no_history", lang))
        return

    settings = await database.get_user_settings(user_id)
    profile = await database.get_user_profile(user_id)

    # Group by date (first 10 chars of ISO timestamp)
    by_date: dict[str, list[dict]] = {}
    for m in meals:
        date = m["timestamp"][:10]
        by_date.setdefault(date, []).append(m)

    lines = []
    for date, day_meals in sorted(by_date.items()):
        cal, p, f_, c = _sum_macros(day_meals)

        if profile:
            tc = profile["target_calories"]
            pct = round(cal / tc * 100) if tc else 0
            icon = "✅" if 80 <= pct <= 120 else "⚠️" if pct > 120 else "❌"
            nutrition = _format_nutrition(cal, p, f_, c, settings, lang)
            lines.append(f"{icon} {date}: {nutrition}" if nutrition else f"{icon} {date}")
        else:
            nutrition = _format_nutrition(cal, p, f_, c, settings, lang)
            lines.append(f"• {date}: {nutrition}" if nutrition else f"• {date}: {cal} kcal")

    await update.message.reply_text(
        t("history_header", lang) + "\n\n" + "\n".join(lines),
        parse_mode="Markdown",
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show display settings with toggle buttons."""
    user_id = update.effective_user.id
    lang = await resolve_language(update)
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
    lang = await resolve_language(update)

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


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language picker button presses."""
    query = update.callback_query
    await query.answer()

    new_lang = query.data.removeprefix("lang:")
    user_id = query.from_user.id

    await database.set_language(user_id, new_lang)

    settings = await database.get_user_settings(user_id)
    await query.edit_message_text(
        t("settings_header", new_lang),
        parse_mode="Markdown",
        reply_markup=_settings_keyboard(settings, new_lang),
    )
