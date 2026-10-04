"""backend/config/default.toml phải đủ khóa và đúng kiểu — documents/CONTEXT.md §6."""

import importlib.util
import tomllib

import pytest

from tests._helpers import PROJECT_ROOT

CFG = tomllib.loads(
    (PROJECT_ROOT / "backend" / "config" / "default.toml").read_text(encoding="utf-8")
)

REQUIRED = {
    ("window", "width"): int,
    ("window", "height"): int,
    ("window", "fps"): int,
    ("game", "random_opening_plies"): int,
    ("game", "max_plies"): int,
    ("game", "claim_draw"): bool,
    ("ranking", "elo_initial"): int,
    ("ranking", "elo_k"): int,
    ("history", "max_games"): int,
    ("ui", "language"): str,
    ("ui", "sound_enabled"): bool,
    ("ui", "piece_set"): str,
    ("ui", "theme"): str,
    ("ui", "bot_move_delay_ms"): int,
    ("ui", "replay_delay_ms"): int,
    ("ui", "show_debug_bots"): bool,
    ("eval_bar", "scale"): float,
}


@pytest.mark.parametrize(("key", "typ"), list(REQUIRED.items()), ids=lambda k: str(k))
def test_required_key(key, typ):
    section, name = key
    assert section in CFG, f"thiếu bảng [{section}]"
    assert name in CFG[section], f"thiếu {section}.{name}"
    assert type(CFG[section][name]) is typ, f"{section}.{name} phải là {typ.__name__}"


def test_value_ranges():
    assert CFG["window"]["width"] * 2 == CFG["window"]["height"] * 3  # tỷ lệ 3:2
    assert CFG["game"]["max_plies"] > 0
    assert CFG["game"]["random_opening_plies"] >= 0
    assert CFG["history"]["max_games"] > 0
    assert CFG["ui"]["language"] in {"vi", "en"}
    assert CFG["ui"]["theme"] in {"dark_winter", "dark_cold", "cold", "fall", "summer", "winter"}
    assert CFG["eval_bar"]["scale"] > 0


def test_sound_off_by_default():
    assert CFG["ui"]["sound_enabled"] is False


def test_every_registered_bot_has_config_table():
    if importlib.util.find_spec("ai.registry") is None:
        pytest.skip("ai.registry chưa được triển khai")
    from ai import registry

    for bot_id in registry.list_bots(include_debug=True):
        assert bot_id in CFG.get("bots", {}), f"thiếu bảng [bots.{bot_id}]"
