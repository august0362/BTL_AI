"""Physical viewport size, click mapping, and live theme regression tests."""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess
import pytest

from core.config import load_config
from gui.app import App
from gui.board_geometry import square_origin
from gui.theme import THEMES


def wait_for(app: App, predicate) -> None:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        app.render_frame()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("controller did not reach the expected state")


@pytest.mark.parametrize("size", [(960, 640), (1440, 960), (1920, 1080)])
def test_physical_canvas_and_window_clicks(size, tmp_path):
    config = load_config(local_path=None)
    config["ui"]["show_debug_bots"] = True
    config["window"].update(width=size[0], height=size[1])
    app = App(config=config, data_dir=tmp_path)
    try:
        assert app.canvas_size == (app.viewport.width, app.viewport.height)
        assert app.render_scale == app.viewport.scale
        app.start_human_game("random", chess.WHITE)
        wait_for(app, lambda: app.controller.snapshot().waiting_for_human)
        x, y = square_origin(chess.E2)
        app.click_window(*app.viewport.to_window(x + 40, y + 40))
        assert app.screen.input.selected == chess.E2
    finally:
        app.quit()


def test_theme_persists_and_updates_board_palette(tmp_path):
    config = load_config(local_path=None)
    local_config = tmp_path / "local.toml"
    app = App(config=config, data_dir=tmp_path / "data", local_config_path=local_config)
    try:
        app.config["ui"]["show_debug_bots"] = True
        app.start_human_game("random", chess.WHITE)
        app.set_theme("cold")
        assert app.theme.id == "cold"
        assert (
            app.screen.board_view.theme.roles["board_light"] == THEMES["cold"].roles["board_light"]
        )
        saved = local_config.read_text(encoding="utf-8")
        assert 'theme = "cold"' in saved
    finally:
        app.quit()
