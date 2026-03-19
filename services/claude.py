"""
Claude API service — calorie estimation with per-user conversation state.

Responses are structured JSON matching CalorieEstimate. The clarifying loop
is driven by callers (handlers/food.py): if clarifying_question is set, the
caller replies and returns without logging; on the next message the existing
conversation history is sent again so Claude has context.
"""

import json
import os
import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

# Lazy-initialised so the module can be imported in tests without a valid key.
_client: AsyncAnthropic | None = None

def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client

# Per-user conversation history: list of {"role": ..., "content": ...} dicts
_conversations: dict[int, list[dict]] = {}

# Per-user language code for system prompt customisation
_user_languages: dict[int, str] = {}

_SYSTEM_PROMPT = """\
You are a calorie and macronutrient estimation assistant. When the user describes food or sends a photo,
estimate its calorie and macronutrient content and respond ONLY with raw JSON — no markdown, no code fences,
no explanation. Use exactly this format:
{{"food_items": ["item 1", "item 2"], "calories_estimate": 450, "proteins_g": 20, "fats_g": 15, "carbohydrates_g": 60, "confidence": 0.8, "clarifying_question": null}}
If the photo shows a nutrition label or packaging, read the values directly from the label
instead of estimating. Use the serving size and number of servings to compute per-item totals.
If the label lists values per 100g/ml but the package size differs, ask the user how much they consumed.
If you need more information to make a reasonable estimate, set clarifying_question to a
short specific question and set calories_estimate, proteins_g, fats_g, carbohydrates_g to null.
confidence is a float between 0 and 1.
IMPORTANT: The food_items list and any clarifying_question MUST be in {language}. Always respond in {language}.
"""


@dataclass
class CalorieEstimate:
    food_items: list[str]
    calories_estimate: int | None
    proteins_g: int | None
    fats_g: int | None
    carbohydrates_g: int | None
    confidence: float
    clarifying_question: str | None


def _parse_response(text: str) -> CalorieEstimate:
    """Parse Claude's JSON response into a CalorieEstimate.

    Strips markdown code fences defensively in case Claude ignores the prompt.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    data = json.loads(cleaned)
    raw_calories = data.get("calories_estimate")

    def _to_int(val):
        return int(val) if val is not None else None

    return CalorieEstimate(
        food_items=data.get("food_items", []),
        calories_estimate=_to_int(raw_calories),
        proteins_g=_to_int(data.get("proteins_g")),
        fats_g=_to_int(data.get("fats_g")),
        carbohydrates_g=_to_int(data.get("carbohydrates_g")),
        confidence=data.get("confidence", 0.0),
        clarifying_question=data.get("clarifying_question"),
    )


_LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "ru": "Russian",
}


def _get_language_name(lang: str | None) -> str:
    """Return the full language name for the system prompt."""
    if not lang:
        return "English"
    code = lang.lower().split("-")[0]
    return _LANGUAGE_NAMES.get(code, "English")


async def _call_claude(user_id: int) -> CalorieEstimate:
    """Send the current conversation history for user_id to Claude and return the estimate."""
    lang_name = _get_language_name(_user_languages.get(user_id))
    system = _SYSTEM_PROMPT.format(language=lang_name)
    response = await _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=system,
        messages=_conversations[user_id],
    )
    reply_text = response.content[0].text
    _conversations[user_id].append({"role": "assistant", "content": reply_text})
    return _parse_response(reply_text)


async def estimate_from_text(user_id: int, text: str, language_code: str | None = None) -> CalorieEstimate:
    """Estimate calories from a text food description.

    Appends the user message to the conversation history so follow-up
    clarifying answers are sent with full context.

    Args:
        user_id: Telegram user ID used as the conversation key.
        text: The user's food description or clarifying answer.
        language_code: Telegram language_code of the user.

    Returns:
        CalorieEstimate — check clarifying_question before logging.
    """
    if user_id not in _conversations:
        _conversations[user_id] = []
    if language_code is not None:
        _user_languages[user_id] = language_code
    _conversations[user_id].append({"role": "user", "content": text})
    return await _call_claude(user_id)


async def estimate_from_photo(
    user_id: int, image_b64: str, caption: str | None, language_code: str | None = None
) -> CalorieEstimate:
    """Estimate calories from a food photo (base64-encoded JPEG).

    Args:
        user_id: Telegram user ID used as the conversation key.
        image_b64: Base64-encoded image string from utils.photos.photo_to_base64.
        caption: Optional text caption the user sent with the photo.
        language_code: Telegram language_code of the user.

    Returns:
        CalorieEstimate — check clarifying_question before logging.
    """
    content: list[dict] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_b64,
            },
        },
    ]
    if caption:
        content.append({"type": "text", "text": caption})
    else:
        content.append({"type": "text", "text": "Analyse this image. If it shows a nutrition label or packaging, read the values from it. Otherwise, estimate the calories and macros of the food shown."})

    if user_id not in _conversations:
        _conversations[user_id] = []
    if language_code is not None:
        _user_languages[user_id] = language_code
    _conversations[user_id].append({"role": "user", "content": content})
    return await _call_claude(user_id)


def clear_conversation(user_id: int) -> None:
    """Delete the conversation history for a user (call after successful logging)."""
    _conversations.pop(user_id, None)
    _user_languages.pop(user_id, None)


def has_active_conversation(user_id: int) -> bool:
    """Return True if the user has an in-progress clarifying-question exchange."""
    return user_id in _conversations and len(_conversations[user_id]) > 0
