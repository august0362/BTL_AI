"""Headless coverage for finished-game controls and Bot vs Bot speed persistence."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess
import pytest

from core.config import load_config
from gui.app import App
from gui.controller import ControllerSnapshot
from gui.screens.game import GameScreen


@pytest.fixture
def app(tmp_path: Path) -> Iterator[App]:
    """Create an isolated headless app with a temporary local config file."""
    config = load_config(local_path=None)
    config["ui"].update(show_debug_bots=True, bot_move_delay_ms=0)
    instance = App(config, tmp_path / "data", tmp_path / "local.toml")
    yield instance
    instance.quit()


def finished_bot_screen(app: App, delay: int = 0) -> tuple[GameScreen, Mock]:
    """Attach a finished bot-game snapshot and return its screen and mock controller."""
    app.config["ui"]["bot_move_delay_ms"] = delay
    app.game_mode = "bot_vs_bot"
    app.white_bot_id = app.black_bot_id = "random"
    controller = Mock()
    controller.snapshot.return_value = ControllerSnapshot(
        board=chess.Board(),
        moves=(),
        game_index=1,
        n_games=1,
        finished_games=(),
        series_result=None,
        thinking=False,
        waiting_for_human=False,
        finished=True,
        paused=False,
    )
    app._controller = controller
    app.goto("game")
    return app.screen, controller


def test_finished_bot_speed_button_cycles_from_zero(app: App) -> None:
    screen, controller = finished_bot_screen(app)

    app.click_logical(*screen.speed_button_rect.center)

    assert app.config["ui"]["bot_move_delay_ms"] == 150
    assert screen.speed_button.label == "Tốc độ: 150"
    controller.set_bot_move_delay.assert_called_once_with(150)


def test_finished_bot_speed_button_keeps_cycling(app: App) -> None:
    screen, controller = finished_bot_screen(app, delay=150)

    app.click_logical(*screen.speed_button_rect.center)

    assert app.config["ui"]["bot_move_delay_ms"] == 300
    assert screen.speed_button.label == "Tốc độ: 300"
    controller.set_bot_move_delay.assert_called_once_with(300)


def test_finished_game_sound_button_still_toggles(app: App) -> None:
    screen, _ = finished_bot_screen(app)
    app.config["ui"]["sound_enabled"] = False
    app.sound.enabled = False

    app.click_logical(*screen.speaker_button_rect.center)

    assert app.sound_enabled
    assert app.sound.enabled


def test_set_bot_move_delay_saves_local_config(app: App, tmp_path: Path) -> None:
    controller = Mock()
    app._controller = controller

    app.set_bot_move_delay(150)

    assert app.config["ui"]["bot_move_delay_ms"] == 150
    saved = tomllib.loads((tmp_path / "local.toml").read_text(encoding="utf-8"))
    assert saved["ui"]["bot_move_delay_ms"] == 150
    controller.set_bot_move_delay.assert_called_once_with(150)


def test_finished_game_ignores_pause_and_stop(app: App) -> None:
    screen, controller = finished_bot_screen(app)

    app.click_logical(*screen.pause_button_rect.center)
    app.click_logical(*screen.stop_button.rect.center)

    controller.pause.assert_not_called()
    controller.resume.assert_not_called()
    controller.stop.assert_not_called()


def test_finished_game_panel_and_bottom_menu_still_work(app: App) -> None:
    screen, _ = finished_bot_screen(app)
    section = screen.sections["players"]
    was_expanded = section.expanded

    app.click_logical(section.rect.left + 30, section.rect.top + 20)
    assert section.expanded is not was_expanded

    app.click_logical(*screen.menu_button.rect.center)
    assert app.current_screen_name == "menu"
