"""Tests for main.py bootstrap helpers."""

import pytest
from unittest.mock import patch
from telegram.ext import filters


def _import_build_allowlist():
    # Import fresh each time so monkeypatching env vars takes effect
    import importlib
    import main as m
    importlib.reload(m)
    return m._build_allowlist


async def test_allowlist_unset_returns_all_filter(monkeypatch):
    monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
    build = _import_build_allowlist()
    f = build()
    assert f is filters.ALL


async def test_allowlist_single_id(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "42")
    build = _import_build_allowlist()
    f = build()
    assert isinstance(f, filters.User)


async def test_allowlist_multiple_ids(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "1,2,3")
    build = _import_build_allowlist()
    f = build()
    assert isinstance(f, filters.User)


async def test_allowlist_ignores_whitespace(monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", " 10 , 20 ")
    build = _import_build_allowlist()
    f = build()
    assert isinstance(f, filters.User)
