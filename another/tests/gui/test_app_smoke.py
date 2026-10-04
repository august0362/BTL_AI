"""Smoke test ứng dụng Pygame ở chế độ không màn hình — documents/CONTEXT.md §5.10."""

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess  # noqa: E402
import pytest  # noqa: E402

from tests._helpers import require_module  # noqa: E402

app_mod = require_module("gui.app")
config_mod = require_module("core.config")
geo = require_module("gui.board_geometry")


@pytest.fixture
def app(tmp_path):
    cfg = config_mod.load_config(local_path=None)
    cfg["ui"]["show_debug_bots"] = True
    cfg["ui"]["language"] = "vi"
    a = app_mod.App(config=cfg, data_dir=tmp_path)
    yield a
    a.quit()


def center(square, flipped=False):
    x, y = geo.square_origin(square, flipped=flipped)
    return x + 40, y + 40


def frames_until(app, pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.render_frame()
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_starts_on_menu_and_renders(app):
    assert app.current_screen_name == "menu"
    app.render_frame()
    assert app.translator.language == "vi"


def test_render_each_mvp_screen(app):
    for name in ("menu", "setup_human"):
        app.goto(name)
        assert app.current_screen_name == name
        app.render_frame()


def waiting(app):
    return app.controller.snapshot().waiting_for_human


def test_play_move_against_random_bot(app):
    app.start_human_game("random", chess.WHITE)
    assert app.current_screen_name == "game"
    assert frames_until(app, lambda: waiting(app))
    app.click_logical(*center(chess.E2))
    app.click_logical(*center(chess.E4))
    assert frames_until(app, lambda: len(app.controller.snapshot().moves) >= 2)
    assert app.controller.snapshot().moves[0].uci == "e2e4"


def test_board_flipped_for_black(app):
    app.start_human_game("random", chess.BLACK)
    assert frames_until(app, lambda: waiting(app))
    board = app.controller.snapshot().board
    move = next(m for m in board.legal_moves if m.uci() in {"e7e5", "e7e6", "d7d6", "g8f6"})
    app.click_logical(*center(move.from_square, flipped=True))
    app.click_logical(*center(move.to_square, flipped=True))
    assert frames_until(app, lambda: len(app.controller.snapshot().moves) >= 3)
    assert app.controller.snapshot().moves[1].uci == move.uci()


def test_click_after_resize(app):
    app.resize(1920, 1080)
    app.render_frame()
    app.start_human_game("random", chess.WHITE)
    from gui.scaling import Viewport

    vp = Viewport.fit(1920, 1080)
    assert frames_until(app, lambda: waiting(app))
    app.click_window(*vp.to_window(*center(chess.D2)))
    app.click_window(*vp.to_window(*center(chess.D4)))
    assert frames_until(app, lambda: len(app.controller.snapshot().moves) >= 1)
    assert app.controller.snapshot().moves[0].uci == "d2d4"


def test_return_to_menu_stops_game(app):
    app.start_human_game("random", chess.WHITE)
    controller = app.controller
    app.goto("menu")
    assert controller.join(5)
    assert app.current_screen_name == "menu"
