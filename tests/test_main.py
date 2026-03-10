"""Tests for main.py bootstrap helpers."""

import pytest
from unittest.mock import patch
from telegram.ext import filters

import main


async def test_allowlist_unset_returns_all_filter():
    with patch("main.os.getenv", return_value=""):
        f = main._build_allowlist()
    assert f is filters.ALL


async def test_allowlist_single_id():
    with patch("main.os.getenv", return_value="42"):
        f = main._build_allowlist()
    assert isinstance(f, filters.User)


async def test_allowlist_multiple_ids():
    with patch("main.os.getenv", return_value="1,2,3"):
        f = main._build_allowlist()
    assert isinstance(f, filters.User)


async def test_allowlist_ignores_whitespace():
    with patch("main.os.getenv", return_value=" 10 , 20 "):
        f = main._build_allowlist()
    assert isinstance(f, filters.User)
