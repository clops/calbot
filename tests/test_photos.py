"""Tests for utils/photos.py"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.photos import photo_to_base64


@pytest.fixture
def photo():
    p = MagicMock()
    p.file_id = "test-file-id"
    return p


@pytest.fixture
def bot(photo):
    """Bot mock that returns a file whose download_as_bytearray returns raw bytes."""
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake-image-data"))

    bot_mock = AsyncMock()
    bot_mock.get_file = AsyncMock(return_value=file_mock)
    return bot_mock


async def test_returns_base64_string(photo, bot):
    result = await photo_to_base64(photo, bot)
    assert isinstance(result, str)
    # Must be valid base64
    decoded = base64.b64decode(result)
    assert decoded == b"fake-image-data"


async def test_uses_photo_file_id(photo, bot):
    await photo_to_base64(photo, bot)
    bot.get_file.assert_awaited_once_with("test-file-id")


async def test_empty_image_returns_empty_base64(bot):
    photo = MagicMock()
    photo.file_id = "empty-file"
    file_mock = AsyncMock()
    file_mock.download_as_bytearray = AsyncMock(return_value=bytearray(b""))
    bot.get_file = AsyncMock(return_value=file_mock)

    result = await photo_to_base64(photo, bot)
    assert result == ""
