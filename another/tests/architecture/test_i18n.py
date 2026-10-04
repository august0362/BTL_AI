"""vi.toml và en.toml phải có cùng tập khóa — documents/CONTEXT.md §5.6."""

import importlib.util
import re
import string
import tomllib

import pytest

from tests._helpers import PROJECT_ROOT

LOCALES_DIR = PROJECT_ROOT / "frontend" / "gui" / "locales"
LANGS = ["vi", "en"]
TERMINATIONS = [
    "checkmate",
    "stalemate",
    "insufficient_material",
    "threefold_repetition",
    "fifty_moves",
    "max_plies",
    "aborted",
]


def flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def load(lang):
    path = LOCALES_DIR / f"{lang}.toml"
    if not path.exists():
        pytest.skip(f"{path.name} chưa được tạo")
    return flatten(tomllib.loads(path.read_text(encoding="utf-8")))


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_same_keys():
    vi, en = load("vi"), load("en")
    assert set(vi) - set(en) == set(), "khóa có trong vi nhưng thiếu trong en"
    assert set(en) - set(vi) == set(), "khóa có trong en nhưng thiếu trong vi"


@pytest.mark.parametrize("lang", LANGS)
def test_values_are_non_empty_strings(lang):
    for key, value in load(lang).items():
        assert isinstance(value, str) and value.strip(), f"{lang}: {key} rỗng"


def test_same_placeholders():
    vi, en = load("vi"), load("en")
    for key in set(vi) & set(en):
        assert placeholders(vi[key]) == placeholders(en[key]), f"{key}: tham số {{}} khác nhau"


@pytest.mark.parametrize("lang", LANGS)
def test_every_termination_translated(lang):
    keys = load(lang)
    for t in TERMINATIONS:
        assert f"termination.{t}" in keys


@pytest.mark.parametrize("lang", LANGS)
def test_every_player_translated(lang):
    if importlib.util.find_spec("ai.registry") is None:
        pytest.skip("ai.registry chưa được triển khai")
    from ai import registry

    keys = load(lang)
    for bot_id in registry.list_bots(include_debug=True) + ["human"]:
        assert f"players.{bot_id}" in keys


def test_keys_are_snake_case():
    for key in load("vi"):
        assert re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)*", key), key


@pytest.mark.parametrize("lang", LANGS)
def test_no_mojibake(lang):
    # Ghi file bằng encoding sai biến chữ có dấu thành "?" (vd "T?nh n?ng").
    for key, value in load(lang).items():
        assert "�" not in value, f"{lang}: {key} có ký tự lỗi mã hóa"
        assert not re.search(r"\w\?\w", value), f"{lang}: {key} có dấu '?' giữa chữ: {value!r}"
