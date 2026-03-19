"""Guided /profile conversation for setting up daily nutritional targets."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from services import database
from services.nutrition import calculate_targets
from utils.helpers import get_user_lang
from utils.i18n import t

logger = logging.getLogger(__name__)

WEIGHT, HEIGHT, AGE, SEX, ACTIVITY, GOAL = range(6)

_PROFILE_KEYS = (
    "profile_weight", "profile_height", "profile_age",
    "profile_sex", "profile_activity", "profile_goal",
)


def _clear_profile_data(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in _PROFILE_KEYS:
        context.user_data.pop(key, None)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point: start the profile setup flow."""
    await update.message.reply_text(t("profile_weight", get_user_lang(update)))
    return WEIGHT


async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(update)
    try:
        weight = float(update.message.text.replace(",", "."))
        if not 30 <= weight <= 300:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("profile_weight_error", lang))
        return WEIGHT

    context.user_data["profile_weight"] = weight
    await update.message.reply_text(t("profile_height", lang))
    return HEIGHT


async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(update)
    try:
        height = float(update.message.text.replace(",", "."))
        if not 100 <= height <= 250:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("profile_height_error", lang))
        return HEIGHT

    context.user_data["profile_height"] = height
    await update.message.reply_text(t("profile_age", lang))
    return AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = get_user_lang(update)
    try:
        age = int(update.message.text)
        if not 10 <= age <= 120:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(t("profile_age_error", lang))
        return AGE

    context.user_data["profile_age"] = age
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("profile_male", lang), callback_data="profile_sex:male"),
         InlineKeyboardButton(t("profile_female", lang), callback_data="profile_sex:female")],
    ])
    await update.message.reply_text(t("profile_sex", lang), reply_markup=keyboard)
    return SEX


async def receive_sex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(update)

    sex = query.data.removeprefix("profile_sex:")
    context.user_data["profile_sex"] = sex

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("profile_sedentary", lang), callback_data="profile_activity:sedentary")],
        [InlineKeyboardButton(t("profile_light", lang), callback_data="profile_activity:light")],
        [InlineKeyboardButton(t("profile_moderate", lang), callback_data="profile_activity:moderate")],
        [InlineKeyboardButton(t("profile_active", lang), callback_data="profile_activity:active")],
    ])
    await query.edit_message_text(t("profile_activity", lang), reply_markup=keyboard)
    return ACTIVITY


async def receive_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(update)

    activity = query.data.removeprefix("profile_activity:")
    context.user_data["profile_activity"] = activity

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(t("profile_lose", lang), callback_data="profile_goal:lose")],
        [InlineKeyboardButton(t("profile_maintain", lang), callback_data="profile_goal:maintain")],
        [InlineKeyboardButton(t("profile_gain", lang), callback_data="profile_goal:gain")],
    ])
    await query.edit_message_text(t("profile_goal", lang), reply_markup=keyboard)
    return GOAL


async def receive_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_lang(update)

    goal = query.data.removeprefix("profile_goal:")
    user_id = query.from_user.id

    weight = context.user_data["profile_weight"]
    height = context.user_data["profile_height"]
    age = context.user_data["profile_age"]
    sex = context.user_data["profile_sex"]
    activity = context.user_data["profile_activity"]

    targets = calculate_targets(weight, height, age, sex, activity, goal)

    await database.save_user_profile(
        user_id=user_id,
        weight_kg=weight,
        height_cm=height,
        age=age,
        sex=sex,
        activity_level=activity,
        goal=goal,
        targets=targets,
    )

    _clear_profile_data(context)

    tc = targets["target_calories"]
    tp = targets["target_proteins"]
    tf = targets["target_fats"]
    tcarbs = targets["target_carbs"]

    await query.edit_message_text(
        t("profile_saved", lang, cal=tc, p=tp, f=tf, c=tcarbs)
    )
    return ConversationHandler.END


async def cancel_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the profile setup flow."""
    _clear_profile_data(context)
    await update.message.reply_text(t("profile_cancelled", get_user_lang(update)))
    return ConversationHandler.END


def build_profile_conversation(allowed_filter: filters.BaseFilter) -> ConversationHandler:
    """Build and return the ConversationHandler for /profile."""
    return ConversationHandler(
        entry_points=[CommandHandler("profile", cmd_profile, filters=allowed_filter)],
        states={
            WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weight)],
            HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_height)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_age)],
            SEX: [CallbackQueryHandler(receive_sex, pattern="^profile_sex:")],
            ACTIVITY: [CallbackQueryHandler(receive_activity, pattern="^profile_activity:")],
            GOAL: [CallbackQueryHandler(receive_goal, pattern="^profile_goal:")],
        },
        fallbacks=[CommandHandler("cancel", cancel_profile)],
        conversation_timeout=300,
    )
