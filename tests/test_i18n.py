"""Tests for utils/i18n.py"""

from utils.i18n import t, _normalise_lang


# ---------------------------------------------------------------------------
# _normalise_lang
# ---------------------------------------------------------------------------

class TestNormaliseLang:
    def test_none_defaults_to_en(self):
        assert _normalise_lang(None) == "en"

    def test_empty_string_defaults_to_en(self):
        assert _normalise_lang("") == "en"

    def test_german(self):
        assert _normalise_lang("de") == "de"

    def test_german_region(self):
        assert _normalise_lang("de-AT") == "de"

    def test_russian(self):
        assert _normalise_lang("ru") == "ru"

    def test_russian_region(self):
        assert _normalise_lang("ru-RU") == "ru"

    def test_unsupported_falls_back_to_en(self):
        assert _normalise_lang("fr") == "en"

    def test_case_insensitive(self):
        assert _normalise_lang("DE") == "de"


# ---------------------------------------------------------------------------
# t()
# ---------------------------------------------------------------------------

class TestTranslate:
    def test_known_key_english(self):
        result = t("estimating", "en")
        assert "Estimating" in result

    def test_known_key_german(self):
        result = t("estimating", "de")
        assert "Nährwerte" in result

    def test_known_key_russian(self):
        result = t("estimating", "ru")
        assert "Оцениваю" in result

    def test_unknown_key_returns_bracket_fallback(self):
        result = t("nonexistent_key", "en")
        assert result == "[nonexistent_key]"

    def test_none_lang_uses_english(self):
        result = t("estimating", None)
        assert "Estimating" in result

    def test_format_kwargs(self):
        result = t("msg_too_long", "en", limit=500)
        assert "500" in result

    def test_fallback_to_english_for_missing_lang_entry(self):
        # All keys have en, de, ru — but test the fallback mechanism
        # by verifying unsupported lang gets English
        result = t("estimating", "fr")
        assert "Estimating" in result
