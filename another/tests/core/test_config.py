"""Đặc tả backend/core/config.py — documents/CONTEXT.md §6."""

import tomllib

from tests._helpers import require_module

config = require_module("core.config")

DEFAULT = """
[window]
width = 960
height = 640

[ui]
language = "vi"
sound_enabled = false

[bots.deep_rl]
device = "cpu"
"""


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return path


def test_load_default_only_when_local_missing(tmp_path):
    d = write(tmp_path / "default.toml", DEFAULT)
    cfg = config.load_config(d, tmp_path / "local.toml")
    assert cfg == tomllib.loads(DEFAULT)


def test_local_overrides_single_nested_key(tmp_path):
    d = write(tmp_path / "default.toml", DEFAULT)
    loc = write(tmp_path / "local.toml", '[ui]\nlanguage = "en"\n')
    cfg = config.load_config(d, loc)
    assert cfg["ui"] == {"language": "en", "sound_enabled": False}
    assert cfg["window"]["width"] == 960


def test_deep_merge_does_not_mutate_inputs():
    base = {"a": {"x": 1, "y": 2}}
    over = {"a": {"y": 3}, "b": 4}
    merged = config.deep_merge(base, over)
    assert merged == {"a": {"x": 1, "y": 3}, "b": 4}
    assert base == {"a": {"x": 1, "y": 2}}
    assert over == {"a": {"y": 3}, "b": 4}


def test_save_local_config_creates_and_merges(tmp_path):
    d = write(tmp_path / "default.toml", DEFAULT)
    loc = tmp_path / "local.toml"
    config.save_local_config({"ui": {"language": "en"}}, loc)
    config.save_local_config({"ui": {"sound_enabled": True}}, loc)
    # Lần lưu thứ 2 không được xóa khóa của lần 1.
    assert tomllib.loads(loc.read_text(encoding="utf-8")) == {
        "ui": {"language": "en", "sound_enabled": True}
    }
    cfg = config.load_config(d, loc)
    assert cfg["ui"] == {"language": "en", "sound_enabled": True}


def test_load_config_defaults_to_repo_files():
    cfg = config.load_config(local_path=None)
    assert cfg["window"]["width"] == 960
    assert cfg["window"]["height"] == 640


def test_get_bot_config(tmp_path):
    d = write(tmp_path / "default.toml", DEFAULT)
    cfg = config.load_config(d, tmp_path / "missing.toml")
    assert config.get_bot_config(cfg, "deep_rl") == {"device": "cpu"}
    assert config.get_bot_config(cfg, "unknown") == {}
