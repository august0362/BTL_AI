"""Tests for configured Deep RL weight summaries and Settings integration."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests._helpers import require_module

weights_mod = require_module("gui.weights_info")
config_mod = require_module("core.config")
app_mod = require_module("gui.app")
translator_mod = require_module("gui.i18n")


def test_weights_rows_decode_and_localize_configured_weights():
    translator = translator_mod.Translator("vi")
    config = {
        "bots": {
            "deep_rl": {
                "weights_url": "file:///models/deeprl%20Ti%E1%BA%BFng%20Vi%E1%BB%87t.pt",
                "weights_sha256": "0123456789abcdef",
                "depth": 1,
            },
            "custom": {
                "display_name": "Custom bot",
                "class": "local.Bot",
                "weights_url": "https://example.test/releases/a%20b.pt",
                "weights_sha256": "abcdef012345",
            },
            "disabled": {"weights_url": "https://example.test/no.pt", "enabled": False},
            "empty": {"weights_url": "", "depth": 2},
        }
    }

    rows = weights_mod.weights_rows(config, translator)

    assert [row.bot_id for row in rows] == ["deep_rl", "custom", "empty"]
    assert rows[0].name == translator.t("players.deep_rl")
    assert rows[0].file == "deeprl Tiếng Việt.pt"
    assert rows[0].source == "trên máy"
    assert rows[0].sha256 == "01234567"
    assert rows[0].depth == "1"
    assert (rows[1].name, rows[1].file, rows[1].source) == (
        "Custom bot",
        "a b.pt",
        "GitHub Release",
    )
    assert rows[1].sha256 == "abcdef01"
    assert rows[1].depth == "3"
    assert rows[2].file == translator.t("settings.weights_none")
    assert rows[2].source == ""
    assert rows[2].depth == "2"


def test_settings_weights_toggle_persists_and_panel_stays_in_canvas(tmp_path):
    config = config_mod.load_config(local_path=None)
    config["bots"] = {
        f"deep_{index}": {"weights_url": f"https://example.test/model_{index}.pt"}
        for index in range(6)
    }
    local_path = tmp_path / "local.toml"
    app = app_mod.App(config=config, data_dir=tmp_path / "data", local_config_path=local_path)
    try:
        app.goto("settings")
        screen = app.screen
        assert not app.config["ui"].get("show_weights_info", False)
        screen.handle_click(*screen.weights.rect.center)
        assert app.config["ui"]["show_weights_info"] is True
        assert "show_weights_info = true" in local_path.read_text(encoding="utf-8")
        app.render_frame()
        assert screen.theme_area.bottom <= 632
        assert screen.theme_area.colliderect(screen.sound.rect) is False
        assert screen.theme_area.colliderect(screen.speed.rect) is False
        assert screen.theme_area.colliderect(screen.back.rect) is False
        screen.handle_click(*screen.weights.rect.center)
        assert app.config["ui"]["show_weights_info"] is False
        assert screen.theme_area.bottom <= 632
    finally:
        app.quit()
