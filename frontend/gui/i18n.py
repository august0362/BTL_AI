"""Small TOML-backed translation helper for the GUI."""

from __future__ import annotations

import tomllib
from pathlib import Path

SUPPORTED_LANGUAGES = ("vi", "en")
LOCALES_DIR = Path(__file__).parent / "locales"


class _MissingParams(dict[str, object]):
    """Keep unknown format fields visible in translated strings."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _flatten(values: dict[str, object], prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in values.items():
        dotted_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flattened.update(_flatten(value, dotted_key + "."))
        elif isinstance(value, str):
            flattened[dotted_key] = value
        else:
            raise ValueError(f"locale value for {dotted_key!r} must be a string")
    return flattened


class Translator:
    """Load and serve strings from the selected locale TOML file."""

    def __init__(
        self,
        language: str = "vi",
        directory: Path = LOCALES_DIR,
        overrides: dict[str, str] | None = None,
    ) -> None:
        self._directory = Path(directory)
        self._language = "vi"
        self._strings: dict[str, str] = {}
        self._overrides = dict(overrides or {})
        self.set_language(language)

    @property
    def language(self) -> str:
        """Return the active language code."""
        return self._language

    def set_language(self, language: str) -> None:
        """Load a supported language, leaving the current one intact on invalid input."""
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"unsupported language: {language}")
        path = self._directory / f"{language}.toml"
        strings = _flatten(tomllib.loads(path.read_text(encoding="utf-8")))
        self._language = language
        self._strings = strings

    def t(self, key: str, **params: object) -> str:
        """Translate a dotted key and preserve any unresolved format fields.

        ``overrides`` (e.g. bot names from ``[bots.<id>] display_name``) win in every language.
        """
        value = self._overrides.get(key) or self._strings.get(key)
        if value is None:
            return key
        return value.format_map(_MissingParams(params))
