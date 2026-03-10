"""Tests for services/claude.py"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import services.claude as claude_service
from services.claude import (
    CalorieEstimate,
    clear_conversation,
    estimate_from_photo,
    estimate_from_text,
    has_active_conversation,
)


def _make_response(food_items, calories, confidence, clarifying_question=None):
    """Build a mock Anthropic response object."""
    payload = json.dumps({
        "food_items": food_items,
        "calories_estimate": calories,
        "confidence": confidence,
        "clarifying_question": clarifying_question,
    })
    content_block = MagicMock()
    content_block.text = payload
    response = MagicMock()
    response.content = [content_block]
    return response


@pytest.fixture(autouse=True)
def reset_conversations():
    """Wipe conversation state between tests."""
    claude_service._conversations.clear()
    yield
    claude_service._conversations.clear()


@pytest.fixture
def mock_create():
    """Patch _get_client so the Anthropic SDK is never instantiated."""
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock()
    with patch.object(claude_service, "_get_client", return_value=mock_client):
        yield mock_client.messages.create


# ---------------------------------------------------------------------------
# estimate_from_text
# ---------------------------------------------------------------------------

async def test_estimate_from_text_returns_dataclass(mock_create):
    mock_create.return_value = _make_response(["banana"], 90, 0.9)
    result = await estimate_from_text(user_id=1, text="I had a banana")
    assert isinstance(result, CalorieEstimate)
    assert result.food_items == ["banana"]
    assert result.calories_estimate == 90
    assert result.confidence == pytest.approx(0.9)
    assert result.clarifying_question is None


async def test_estimate_from_text_clarifying_question(mock_create):
    mock_create.return_value = _make_response([], None, 0.0, "How large was the portion?")
    result = await estimate_from_text(user_id=2, text="I had some pasta")
    assert result.clarifying_question == "How large was the portion?"
    assert result.calories_estimate is None


async def test_estimate_from_text_builds_conversation_history(mock_create):
    mock_create.return_value = _make_response(["apple"], 80, 0.85)
    await estimate_from_text(user_id=3, text="an apple")
    history = claude_service._conversations[3]
    # user message + assistant reply
    assert history[0] == {"role": "user", "content": "an apple"}
    assert history[1]["role"] == "assistant"


async def test_estimate_from_text_appends_followup(mock_create):
    """Second message must be appended to existing history, not replace it."""
    mock_create.return_value = _make_response([], None, 0.0, "How big?")
    await estimate_from_text(user_id=4, text="pasta")

    mock_create.return_value = _make_response(["pasta"], 400, 0.8)
    await estimate_from_text(user_id=4, text="a large bowl")

    history = claude_service._conversations[4]
    roles = [m["role"] for m in history]
    assert roles == ["user", "assistant", "user", "assistant"]


# ---------------------------------------------------------------------------
# estimate_from_photo
# ---------------------------------------------------------------------------

async def test_estimate_from_photo_returns_dataclass(mock_create):
    mock_create.return_value = _make_response(["pizza"], 800, 0.75)
    result = await estimate_from_photo(user_id=5, image_b64="abc123", caption=None)
    assert result.food_items == ["pizza"]
    assert result.calories_estimate == 800


async def test_estimate_from_photo_with_caption(mock_create):
    mock_create.return_value = _make_response(["salad"], 200, 0.9)
    await estimate_from_photo(user_id=6, image_b64="img", caption="caesar salad")

    history = claude_service._conversations[6]
    user_content = history[0]["content"]
    # Content should be a list with image block + caption text block
    assert any(block.get("type") == "text" and "caesar salad" in block.get("text", "") for block in user_content)


async def test_estimate_from_photo_default_prompt_when_no_caption(mock_create):
    mock_create.return_value = _make_response(["burger"], 600, 0.7)
    await estimate_from_photo(user_id=7, image_b64="img", caption=None)

    history = claude_service._conversations[7]
    user_content = history[0]["content"]
    text_blocks = [b for b in user_content if b.get("type") == "text"]
    assert len(text_blocks) == 1
    assert "calories" in text_blocks[0]["text"].lower()


# ---------------------------------------------------------------------------
# clear_conversation / has_active_conversation
# ---------------------------------------------------------------------------

async def test_has_active_conversation_false_initially():
    assert not has_active_conversation(99)


async def test_has_active_conversation_true_after_message(mock_create):
    mock_create.return_value = _make_response(["egg"], 70, 0.9)
    await estimate_from_text(user_id=10, text="an egg")
    assert has_active_conversation(10)


async def test_clear_conversation_removes_state(mock_create):
    mock_create.return_value = _make_response(["egg"], 70, 0.9)
    await estimate_from_text(user_id=11, text="an egg")
    clear_conversation(11)
    assert not has_active_conversation(11)


def test_clear_conversation_noop_for_unknown_user():
    # Should not raise
    clear_conversation(999)


# ---------------------------------------------------------------------------
# _parse_response — markdown fence stripping
# ---------------------------------------------------------------------------

def test_parse_response_strips_json_fences():
    from services.claude import _parse_response
    text = '```json\n{"food_items": ["apple"], "calories_estimate": 80, "confidence": 0.9, "clarifying_question": null}\n```'
    result = _parse_response(text)
    assert result.food_items == ["apple"]
    assert result.calories_estimate == 80


def test_parse_response_strips_plain_fences():
    from services.claude import _parse_response
    text = '```\n{"food_items": ["rice"], "calories_estimate": 200, "confidence": 0.8, "clarifying_question": null}\n```'
    result = _parse_response(text)
    assert result.food_items == ["rice"]
    assert result.calories_estimate == 200


def test_parse_response_coerces_float_calories():
    from services.claude import _parse_response
    text = '{"food_items": ["pasta"], "calories_estimate": 350.0, "confidence": 0.85, "clarifying_question": null}'
    result = _parse_response(text)
    assert result.calories_estimate == 350
    assert isinstance(result.calories_estimate, int)
