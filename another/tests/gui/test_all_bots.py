"""Headless smoke coverage for all GUI bot choices and Elo records."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import chess
import pytest

from ai import registry
from ai.base_bot import BaseBot, BotUnavailableError
from core.config import load_config
from core.types import GameResult, Termination
from gui.app import App
from gui.assets_loader import get_font
from tournament.records import GameRecord

BOT_IDS = (
    "alphabeta_regression",
    "genetic_alphabeta",
    "mcts",
    "deep_rl",
    "bench_random",
    "bench_alphabeta_material",
    "bench_alphabeta3",
    "bench_alphabeta_tt",
    "bench_alphabeta_custom",
    "bench5_gpt",
    "bench5_gemini",
    "bench5_deepseek",
    "bench5_grok",
    "bench5_hybrid",
    "bench6_gpt",
    "bench6_gemini",
    "bench6_grok",
    "bench6_deepseek",
    "bench7",
)


@pytest.fixture
def app(tmp_path):
    """Create an isolated application with debug bots disabled by default."""
    config = load_config(local_path=None)
    config["ui"]["show_debug_bots"] = False
    # BOT_IDS lists generations up to 7; pin it so the test ignores the chosen display level.
    config.setdefault("benchmarks", {})["max_level"] = 7
    instance = App(config, tmp_path / "data", tmp_path / "local.toml")
    yield instance
    instance.quit()


def _record(white_id: str, black_id: str, winner: chess.Color) -> GameRecord:
    return GameRecord(
        game_id=f"{white_id}-vs-{black_id}",
        started_at="2026-10-07T00:00:00+00:00",
        mode="human_vs_bot" if "human" in (white_id, black_id) else "bot_vs_bot",
        white_id=white_id,
        black_id=black_id,
        white_name=white_id,
        black_name=black_id,
        opening_moves=[],
        moves=[],
        result=GameResult(winner, Termination.CHECKMATE),
    )


def _button_rects(screen) -> list:
    """Return every clickable button rectangle on a setup screen."""
    if hasattr(screen, "bot_buttons"):
        buttons = [
            *screen.bot_buttons,
            *screen.color_buttons,
            screen.start_button,
            screen.back_button,
        ]
    else:
        buttons = [
            *screen.buttons,
            *screen.black_buttons,
            *screen.format_buttons,
            screen.swap,
            screen.start,
            screen.back,
        ]
    return [button.rect for button in buttons]


def test_ranking_contains_all_bots_and_human_at_initial_elo(app: App) -> None:
    """The Elo table starts with each playable bot and human, without baseline."""
    table = app.ranking.table()
    assert {player_id for player_id, _ in table} == {*BOT_IDS, "human"}
    assert len(table) == len(BOT_IDS) + 1
    assert all(stats.elo == app.ranking.elo_initial for _, stats in table)


@pytest.mark.parametrize("screen_name", ["setup_human", "setup_bots"])
def test_setup_screens_list_all_bots_and_fit_buttons(app: App, screen_name: str) -> None:
    """Both setup screens fit every standard bot and the optional debug bot."""
    debug_ids = [*BOT_IDS[:4], "random", *BOT_IDS[4:]]
    for debug_enabled, expected in ((False, list(BOT_IDS)), (True, debug_ids)):
        app.config["ui"]["show_debug_bots"] = debug_enabled
        app.goto(screen_name)
        assert app.screen.bot_ids == expected
        rects = _button_rects(app.screen)
        assert all(pygame_rect.left >= 0 and pygame_rect.top >= 0 for pygame_rect in rects)
        assert all(pygame_rect.right <= 960 and pygame_rect.bottom <= 640 for pygame_rect in rects)
        assert all(
            not first.colliderect(second)
            for index, first in enumerate(rects)
            for second in rects[index + 1 :]
        )


def test_benchmark_games_update_both_elo_profiles(app: App) -> None:
    """Human versus benchmark and benchmark versus member games are rated."""
    assert app.ranking.record_game(_record("human", "bench_alphabeta3", chess.WHITE))
    assert app.ranking.stats("human").elo > 1200
    assert app.ranking.stats("bench_alphabeta3").elo < 1200

    assert app.ranking.record_game(_record("bench_random", "mcts", chess.BLACK))
    assert app.ranking.stats("bench_random").elo < 1200
    assert app.ranking.stats("mcts").elo > 1200


@pytest.mark.parametrize("screen_name", ["setup_human", "setup_bots"])
def test_unavailable_reason_lines_fit_between_rows(app: App, monkeypatch, screen_name: str) -> None:
    """Unavailable reasons fit without touching the next button row."""
    create_bot = registry.create_bot

    def unavailable_one(bot_id: str, config: dict[str, object] | None = None) -> BaseBot:
        if bot_id == "bench_alphabeta3":
            raise BotUnavailableError("test unavailable")
        return create_bot(bot_id, config)

    monkeypatch.setattr(registry, "create_bot", unavailable_one)
    app.goto(screen_name)
    screen = app.screen
    index = screen.bot_ids.index("bench_alphabeta3")
    if screen_name == "setup_human":
        button = screen.bot_buttons[index]
        reason_y = button.rect.bottom + 1
        next_button = screen.bot_buttons[index + 2]
    else:
        button = screen.buttons[index]
        reason_y = button.rect.bottom + 1
        next_button = screen.buttons[index + 1]
    assert reason_y + get_font(9).get_height() <= next_button.rect.top


def test_clicking_benchmark_and_start_opens_game(app: App) -> None:
    """A benchmark selection starts through the regular human game path."""
    app.goto("setup_human")
    screen = app.screen
    index = screen.bot_ids.index("bench_random")
    app.click_logical(*screen.bot_buttons[index].rect.center)
    app.click_logical(*screen.start_button.rect.center)
    assert app.current_screen_name == "game"
    assert app.controller is not None
