"""Headless coverage for the M4 application screens and persistence."""

from __future__ import annotations

import os
import time
import tomllib
from dataclasses import replace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from core.config import load_config
from core.types import GameResult, Termination
from gui.app import App
from tournament.records import GameRecord


@pytest.fixture
def app(tmp_path):
    """Create an isolated application with debug bots available."""
    config = load_config(local_path=None)
    config["ui"].update(show_debug_bots=True, bot_move_delay_ms=0)
    instance = App(config, tmp_path / "data", tmp_path / "local.toml")
    yield instance
    instance.quit()


def wait_finished(app: App, timeout: float = 5.0) -> None:
    """Wait for the active bot series to finish or fail the smoke test."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.render_frame()
        if app.controller.snapshot().finished:
            return
        time.sleep(0.01)
    pytest.fail("bot series did not finish before timeout")


def test_m4_screens_persistence_and_bot_series(app: App, tmp_path) -> None:
    """Render all M4 screens in both languages and exercise their app APIs."""
    app.config["game"].update(max_plies=4, random_opening_plies=0)
    screens = ("menu", "setup_human", "setup_bots", "history", "leaderboard", "settings")
    for language in ("vi", "en"):
        app.set_language(language)
        for name in screens:
            app.goto(name)
            app.render_frame()

    app.set_language("vi")
    app.set_sound_enabled(True)
    app.set_replay_delay(1200)
    saved = tomllib.loads((tmp_path / "local.toml").read_text(encoding="utf-8"))
    assert saved["ui"] == {"language": "vi", "sound_enabled": True, "replay_delay_ms": 1200}

    before = app.ranking.table()
    app.start_bot_game("random", "random", 3)
    controller = app.controller
    wait_finished(app)
    assert controller.join(1)
    assert len(app.history.list()) == 3
    assert app.ranking.table() == before

    record = app.history.list()[0]
    app.open_replay(record.game_id)
    app.replay_model.last()
    app.render_frame()
    app.replay_model.first()
    app.render_frame()
    for language in ("vi", "en"):
        app.set_language(language)
        app.goto("replay")
        app.render_frame()

    # A saved random game is useful for replay; record an equivalent rated game.
    rated_record = replace(record, white_id="human", black_id="mcts")
    assert app.ranking.record_game(rated_record)
    assert app.ranking.stats("human").games == 1
    app.reset_ranking()
    assert app.ranking.stats("human").games == 0

    app.config["ui"]["bot_move_delay_ms"] = 300
    app.config["game"]["max_plies"] = 300
    app.set_language("en")
    app.start_bot_game("random", "random", 3)
    active = app.controller
    app.goto("menu")
    assert active.join(1)
    assert active.snapshot().finished


def test_history_scroll_opens_an_older_game(app: App) -> None:
    """Scrolling the history list opens one of its older visible records."""
    records = []
    for index in range(12):
        record = GameRecord(
            game_id=f"fake-{index:02d}",
            started_at=f"2026-01-{index + 1:02d}T00:00:00+00:00",
            mode="bot_vs_bot",
            white_id="random",
            black_id="random",
            white_name=f"White {index}",
            black_name=f"Black {index}",
            opening_moves=[],
            moves=[],
            result=GameResult(None, Termination.STALEMATE),
        )
        app.history.save(record)
        records.append(record)

    app.goto("history")
    app.scroll_logical(-1)
    last_row = app.screen.rows[-1].rect
    app.click_logical(*last_row.center)

    assert app.replay_model is not None
    older_records = app.history.list()[5:]
    assert app.replay_model._record.game_id in {record.game_id for record in older_records}


def test_bot_game_top_bar_buttons_fit_panel(app: App) -> None:
    """The bot game speaker, pause, and speed controls stay separate in both locales."""
    app.game_mode = "bot_vs_bot"
    app.white_bot_id = app.black_bot_id = "random"
    canvas_rect = app.canvas.get_rect()
    for language in ("vi", "en"):
        app.set_language(language)
        app.goto("game")
        screen = app.screen
        rects = (
            screen.speaker_button_rect,
            screen.pause_button_rect,
            screen.speed_button_rect,
        )
        assert all(canvas_rect.contains(rect) for rect in rects)
        assert not rects[0].colliderect(rects[1])
        assert not rects[0].colliderect(rects[2])
        assert not rects[1].colliderect(rects[2])


def test_every_screen_renders_for_each_discovered_theme(app: App) -> None:
    """Render all screens with each built-in and discovered resource theme."""
    from gui.theme import THEME_IDS

    app.config["game"].update(max_plies=2, random_opening_plies=0)
    app.start_bot_game("random", "random", 1)
    wait_finished(app)
    app.open_replay(app.history.list()[0].game_id)
    screens = (
        "menu",
        "setup_human",
        "setup_bots",
        "history",
        "leaderboard",
        "settings",
        "game",
        "replay",
    )

    for theme_id in THEME_IDS:
        app.set_theme(theme_id)
        for screen_name in screens:
            app.goto(screen_name)
            app.render_frame()
            if screen_name == "settings":
                first_theme = next(iter(app.screen.theme_rects.values()))
                app.screen.handle_hover(*first_theme.center)
                app.render_frame()
                assert app.screen.preview_theme_id is not None
                app.scroll_logical(-1)
                app.render_frame()

    assert app.theme.id in THEME_IDS
