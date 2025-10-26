import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class I18n:
    def __init__(self, language: str = "en"):
        self.language = language
        self.translations: dict[str, Any] = {}
        self.load_language(language)

    def load_language(self, language: str) -> None:
        """Load translations for the specified language."""
        self.language = language
        locale_file = Path(__file__).parent / "locales" / f"{language}.json"

        if not locale_file.exists():
            logger.warning(
                f"Locale file not found: {locale_file}, falling back to English"
            )
            locale_file = Path(__file__).parent / "locales" / "en.json"

        if not locale_file.exists():
            logger.error("English locale file not found, using empty translations")
            self.translations = {}
            return

        try:
            with open(locale_file, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load translations from {locale_file}: {e}")
            self.translations = {}

    def t(self, key: str, default: str | None = None) -> str:
        """Get translation for the given key."""
        value = self.translations.get(key)
        if value is not None:
            return str(value)
        if default is not None:
            return default
        return key


_i18n_instance: I18n | None = None


def init_i18n(language: str = "en") -> I18n:
    """Initialize the global i18n instance."""
    global _i18n_instance
    _i18n_instance = I18n(language)
    return _i18n_instance


def get_i18n() -> I18n:
    """Get the global i18n instance."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18n()
    return _i18n_instance


def t(key: str, default: str | None = None) -> str:
    """Shortcut function to get translation."""
    return get_i18n().t(key, default)
