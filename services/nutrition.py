"""Nutritional target calculations using the Mifflin-St Jeor equation."""

_ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
}

_GOAL_ADJUSTMENTS = {
    "lose": -500,
    "maintain": 0,
    "gain": 500,
}


def calculate_targets(
    weight_kg: float,
    height_cm: float,
    age: int,
    sex: str,
    activity_level: str,
    goal: str,
) -> dict:
    """Calculate daily nutritional targets.

    Returns dict with target_calories, target_proteins, target_fats, target_carbs.
    """
    if sex == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    tdee = bmr * _ACTIVITY_MULTIPLIERS[activity_level]
    target_calories = round(tdee + _GOAL_ADJUSTMENTS[goal])

    target_proteins = round(2 * weight_kg)
    target_fats = round(0.25 * target_calories / 9)
    carb_calories = target_calories - target_proteins * 4 - target_fats * 9
    target_carbs = max(0, round(carb_calories / 4))

    return {
        "target_calories": target_calories,
        "target_proteins": target_proteins,
        "target_fats": target_fats,
        "target_carbs": target_carbs,
    }
