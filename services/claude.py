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

_SYSTEM_PROMPT = """\
You are a calorie estimation assistant. When the user describes food or sends a photo,
estimate its calorie content and respond ONLY with raw JSON — no markdown, no code fences,
no explanation. Use exactly this format:
{"food_items": ["item 1", "item 2"], "calories_estimate": 450, "confidence": 0.8, "clarifying_question": null}
If you need more information to make a reasonable estimate, set clarifying_question to a
short specific question and set calories_estimate to null.
confidence is a float between 0 and 1.
"""


@dataclass
class CalorieEstimate:
    food_items: list[str]
    calories_estimate: int | None
    confidence: float
    clarifying_question: str | None


def _parse_response(text: str) -> CalorieEstimate:
    """Parse Claude's JSON response into a CalorieEstimate.

    Strips markdown code fences defensively in case Claude ignores the prompt.
    """
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    data = json.loads(cleaned)
    raw_calories = data.get("calories_estimate")
    return CalorieEstimate(
        food_items=data.get("food_items", []),
        calories_estimate=int(raw_calories) if raw_calories is not None else None,
        confidence=data.get("confidence", 0.0),
        clarifying_question=data.get("clarifying_question"),
    )


async def _call_claude(user_id: int) -> CalorieEstimate:
    """Send the current conversation history for user_id to Claude and return the estimate."""
    response = await _get_client().messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=_conversations[user_id],
    )
    reply_text = response.content[0].text
    _conversations[user_id].append({"role": "assistant", "content": reply_text})
    return _parse_response(reply_text)


async def estimate_from_text(user_id: int, text: str) -> CalorieEstimate:
    """Estimate calories from a text food description.

    Appends the user message to the conversation history so follow-up
    clarifying answers are sent with full context.

    Args:
        user_id: Telegram user ID used as the conversation key.
        text: The user's food description or clarifying answer.

    Returns:
        CalorieEstimate — check clarifying_question before logging.
    """
    if user_id not in _conversations:
        _conversations[user_id] = []
    _conversations[user_id].append({"role": "user", "content": text})
    return await _call_claude(user_id)


async def estimate_from_photo(
    user_id: int, image_b64: str, caption: str | None
) -> CalorieEstimate:
    """Estimate calories from a food photo (base64-encoded JPEG).

    Args:
        user_id: Telegram user ID used as the conversation key.
        image_b64: Base64-encoded image string from utils.photos.photo_to_base64.
        caption: Optional text caption the user sent with the photo.

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
        content.append({"type": "text", "text": "What food is this and how many calories does it contain?"})

    if user_id not in _conversations:
        _conversations[user_id] = []
    _conversations[user_id].append({"role": "user", "content": content})
    return await _call_claude(user_id)


def clear_conversation(user_id: int) -> None:
    """Delete the conversation history for a user (call after successful logging)."""
    _conversations.pop(user_id, None)


def has_active_conversation(user_id: int) -> bool:
    """Return True if the user has an in-progress clarifying-question exchange."""
    return user_id in _conversations and len(_conversations[user_id]) > 0
