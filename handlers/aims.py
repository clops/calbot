"""Guided /aims conversation for manually setting daily nutritional targets."""

import logging

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services import database
from utils.helpers import resolve_language
from utils.i18n import t

logger = logging.getLogger(__name__)

AIMS_CALORIES, AIMS_PROTEINS, AIMS_FATS, AIMS_CARBS = range(4)

_AIMS_KEYS = ("aims_calories", "aims_proteins", "aims_fats", "aims_carbs")

# Ordered list of (state, settings field, user_data key, prompt i18n key)
_STEPS = [
    (AIMS_CALORIES, "show_calories", "aims_calories", "aims_calories"),
    (AIMS_PROTEINS, "show_proteins", "aims_proteins", "aims_proteins"),
    (AIMS_FATS, "show_fats", "aims_fats", "aims_fats"),
    (AIMS_CARBS, "show_carbohydrates", "aims_carbs", "aims_carbs"),
]


def _clear_aims_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in _AIMS_KEYS:
        context.user_data.pop(key, None)
    context.user_data.pop("aims_settings", None)
    context.user_data.pop("aims_current", None)


async def _prompt_next_or_save(update, context, after_index):
    """Find the next enabled step after after_index, prompt for it, or save if done."""
    lang = await resolve_language(update)
    settings = context.user_data.get("aims_settings", {})
    current_aims = context.user_data.get("aims_current", {})

    # Map data keys to profile fields
    _PROFILE_FIELD = {
        "aims_calories": "target_calories",
        "aims_proteins": "target_proteins",
        "aims_fats": "target_fats",
        "aims_carbs": "target_carbs",
    }

    for state, setting_field, data_key, prompt_key in _STEPS[after_index:]:
        if settings.get(setting_field, True):
            prompt = t(prompt_key, lang)
            profile_field = _PROFILE_FIELD[data_key]
            current_val = current_aims.get(profile_field)
            if current_val is not None and current_val > 0:
                prompt += f" ({t('aims_current', lang, value=current_val)})"
            await update.message.reply_text(prompt)
            return state

    # No more steps — save
    return await _save_aims(update, context, lang)


async def _save_aims(update, context, lang):
    """Save collected aims to the database and end conversation."""
    user_id = update.effective_user.id
    cal = context.user_data.get("aims_calories", 0)
    p = context.user_data.get("aims_proteins", 0)
    f = context.user_data.get("aims_fats", 0)
    c = context.user_data.get("aims_carbs", 0)

    await database.save_user_aims(
        user_id=user_id,
        target_calories=cal,
        target_proteins=p,
        target_fats=f,
        target_carbs=c,
    )

    settings = context.user_data.get("aims_settings", {})
    _clear_aims_data(context)
    parts = []
    if settings.get("show_calories", True):
        parts.append(f"{cal} kcal")
    if settings.get("show_proteins", True):
        parts.append(f"P: {p}g")
    if settings.get("show_fats", True):
        parts.append(f"F: {f}g")
    if settings.get("show_carbohydrates", True):
        parts.append(f"C: {c}g")

    await update.message.reply_text(
        t("aims_saved", lang, targets=" | ".join(parts))
    )
    return ConversationHandler.END


async def cmd_aims(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: start the aims setup flow."""
    lang = await resolve_language(update)
    user_id = update.effective_user.id
    settings = await database.get_user_settings(user_id)
    context.user_data["aims_settings"] = settings

    # Load existing aims so we can show current values in prompts
    profile = await database.get_user_profile(user_id)
    context.user_data["aims_current"] = profile or {}

    # Check if at least one nutrient is enabled
    has_any = any(
        settings.get(field, True) for _, field, _, _ in _STEPS
    )
    if not has_any:
        await update.message.reply_text(t("aims_nothing_enabled", lang))
        return ConversationHandler.END

    return await _prompt_next_or_save(update, context, after_index=0)


async def receive_calories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await resolve_language(update)
    try:
        val = int(update.message.text.strip())
        if not 500 <= val <= 10000:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("aims_calories_error", lang))
        return AIMS_CALORIES

    context.user_data["aims_calories"] = val
    return await _prompt_next_or_save(update, context, after_index=1)


async def receive_proteins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await resolve_language(update)
    try:
        val = int(update.message.text.strip())
        if not 0 <= val <= 1000:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("aims_proteins_error", lang))
        return AIMS_PROTEINS

    context.user_data["aims_proteins"] = val
    return await _prompt_next_or_save(update, context, after_index=2)


async def receive_fats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await resolve_language(update)
    try:
        val = int(update.message.text.strip())
        if not 0 <= val <= 1000:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("aims_fats_error", lang))
        return AIMS_FATS

    context.user_data["aims_fats"] = val
    return await _prompt_next_or_save(update, context, after_index=3)


async def receive_carbs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = await resolve_language(update)
    try:
        val = int(update.message.text.strip())
        if not 0 <= val <= 2000:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("aims_carbs_error", lang))
        return AIMS_CARBS

    context.user_data["aims_carbs"] = val
    return await _prompt_next_or_save(update, context, after_index=4)


async def cancel_aims(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the aims setup flow."""
    _clear_aims_data(context)
    lang = await resolve_language(update)
    await update.message.reply_text(t("aims_cancelled", lang))
    return ConversationHandler.END


def build_aims_conversation(allowed_filter: filters.BaseFilter) -> ConversationHandler:
    """Build and return the ConversationHandler for /aims."""
    return ConversationHandler(
        entry_points=[CommandHandler("aims", cmd_aims, filters=allowed_filter)],
        states={
            AIMS_CALORIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_calories)],
            AIMS_PROTEINS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proteins)],
            AIMS_FATS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_fats)],
            AIMS_CARBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_carbs)],
        },
        fallbacks=[CommandHandler("cancel", cancel_aims)],
        conversation_timeout=300,
    )
