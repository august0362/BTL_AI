"""Đặc tả frontend/gui/i18n.py — documents/CONTEXT.md §5.6, §5.8."""

import pytest

from tests._helpers import require_module

i18n = require_module("gui.i18n")


@pytest.fixture
def tdir(tmp_path):
    (tmp_path / "vi.toml").write_text(
        '[menu]\nquit = "Thoát"\n[game]\nthinking = "{name} đang nghĩ"\n', encoding="utf-8"
    )
    (tmp_path / "en.toml").write_text(
        '[menu]\nquit = "Quit"\n[game]\nthinking = "{name} is thinking"\n', encoding="utf-8"
    )
    return tmp_path


def test_supported_languages():
    assert i18n.SUPPORTED_LANGUAGES == ("vi", "en")


def test_translate_and_switch(tdir):
    tr = i18n.Translator("vi", directory=tdir)
    assert tr.language == "vi"
    assert tr.t("menu.quit") == "Thoát"
    tr.set_language("en")
    assert tr.language == "en"
    assert tr.t("menu.quit") == "Quit"


def test_params(tdir):
    tr = i18n.Translator("en", directory=tdir)
    assert tr.t("game.thinking", name="MCTS") == "MCTS is thinking"


def test_missing_param_does_not_crash(tdir):
    assert i18n.Translator("en", directory=tdir).t("game.thinking") == "{name} is thinking"


def test_missing_key_returns_key(tdir):
    assert i18n.Translator("vi", directory=tdir).t("no.such.key") == "no.such.key"


def test_unsupported_language(tdir):
    with pytest.raises(ValueError):
        i18n.Translator("fr", directory=tdir)
    tr = i18n.Translator("vi", directory=tdir)
    with pytest.raises(ValueError):
        tr.set_language("fr")
    assert tr.language == "vi"


def test_real_files():
    tr = i18n.Translator("vi")
    assert tr.t("menu.quit") == "Thoát"
    tr.set_language("en")
    assert tr.t("menu.quit") == "Quit"
