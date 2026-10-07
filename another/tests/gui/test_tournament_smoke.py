"""Smoke test chạy giải xếp hạng AI ở chế độ không màn hình."""

from __future__ import annotations

import os
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from core.config import load_config
from gui.app import App


@pytest.fixture
def app(tmp_path):
    config = load_config(local_path=None)
    config["ui"].update(show_debug_bots=True, bot_move_delay_ms=0)
    config["tournament"].update(
        bots=["bench_random", "bench_alphabeta3"],
        matches_per_pair=2,
        max_plies=6,
        depth=1,
        random_opening_plies=0,
    )
    instance = App(config, tmp_path / "data", tmp_path / "local.toml")
    yield instance
    instance.tournament.stop()
    instance.tournament.join(5)
    instance.quit()


def wait_finished(app: App, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.render_frame()
        if app.tournament.snapshot().finished:
            return
        time.sleep(0.01)
    pytest.fail("tournament did not finish before timeout")


def test_tournament_runs_in_background_and_is_saved(app):
    app.start_tournament()
    snapshot = app.tournament.snapshot()
    assert snapshot.running is True
    assert snapshot.games_total == 2
    wait_finished(app)

    snapshot = app.tournament.snapshot()
    assert snapshot.running is False
    assert snapshot.stopped is False
    assert snapshot.result is not None
    assert snapshot.result.completed is True
    assert snapshot.result.games_played == 2
    assert snapshot.result.battle == 1
    assert sum(row.points for row in snapshot.standings) == 2.0

    battles = app.tournament_history.list()
    assert [battle.battle for battle in battles] == [1]
    assert battles[0].participants == ("bench_random", "bench_alphabeta3")
    assert len(battles[0].matchups) == 1


def test_tournament_screens_render(app):
    app.start_tournament()
    wait_finished(app)
    for name in ("tournament", "tournament_history"):
        app.goto(name)
        assert app.current_screen_name == name
        app.render_frame()
    app.goto("menu")
    app.render_frame()


def test_stopping_a_tournament_keeps_the_history_untouched(app):
    app.start_tournament()
    app.tournament.stop()
    assert app.tournament.join(60)
    snapshot = app.tournament.snapshot()
    assert snapshot.running is False
    assert snapshot.stopped is True
    assert snapshot.result is not None
    assert snapshot.result.completed is False
    assert app.tournament_history.list() == []
