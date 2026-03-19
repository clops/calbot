"""Tests for utils/helpers.py"""

from unittest.mock import MagicMock

from utils.helpers import get_user_lang


def test_returns_language_code():
    update = MagicMock()
    update.effective_user.language_code = "de"
    assert get_user_lang(update) == "de"


def test_returns_none_when_no_user():
    update = MagicMock()
    update.effective_user = None
    assert get_user_lang(update) is None


def test_returns_language_code_with_region():
    update = MagicMock()
    update.effective_user.language_code = "en-US"
    assert get_user_lang(update) == "en-US"
