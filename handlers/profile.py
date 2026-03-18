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
    await update.message.reply_text("What is your weight in kg?")
    return WEIGHT


async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        weight = float(update.message.text.replace(",", "."))
        if not 30 <= weight <= 300:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid weight between 30 and 300 kg.")
        return WEIGHT

    context.user_data["profile_weight"] = weight
    await update.message.reply_text("What is your height in cm?")
    return HEIGHT


async def receive_height(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        height = float(update.message.text.replace(",", "."))
        if not 100 <= height <= 250:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid height between 100 and 250 cm.")
        return HEIGHT

    context.user_data["profile_height"] = height
    await update.message.reply_text("How old are you?")
    return AGE


async def receive_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        age = int(update.message.text)
        if not 10 <= age <= 120:
            raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text("Please enter a valid age between 10 and 120.")
        return AGE

    context.user_data["profile_age"] = age
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Male", callback_data="profile_sex:male"),
         InlineKeyboardButton("Female", callback_data="profile_sex:female")],
    ])
    await update.message.reply_text("What is your sex?", reply_markup=keyboard)
    return SEX


async def receive_sex(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    sex = query.data.removeprefix("profile_sex:")
    context.user_data["profile_sex"] = sex

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sedentary", callback_data="profile_activity:sedentary")],
        [InlineKeyboardButton("Lightly active", callback_data="profile_activity:light")],
        [InlineKeyboardButton("Moderately active", callback_data="profile_activity:moderate")],
        [InlineKeyboardButton("Very active", callback_data="profile_activity:active")],
    ])
    await query.edit_message_text("What is your activity level?", reply_markup=keyboard)
    return ACTIVITY


async def receive_activity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    activity = query.data.removeprefix("profile_activity:")
    context.user_data["profile_activity"] = activity

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Lose weight", callback_data="profile_goal:lose")],
        [InlineKeyboardButton("Maintain", callback_data="profile_goal:maintain")],
        [InlineKeyboardButton("Gain weight", callback_data="profile_goal:gain")],
    ])
    await query.edit_message_text("What is your goal?", reply_markup=keyboard)
    return GOAL


async def receive_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

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
        f"✅ Profile saved! Your daily targets:\n"
        f"{tc} kcal | P: {tp}g  F: {tf}g  C: {tcarbs}g"
    )
    return ConversationHandler.END


async def cancel_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the profile setup flow."""
    _clear_profile_data(context)
    await update.message.reply_text("Profile setup cancelled.")
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
