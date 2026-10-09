"""Đặc tả đo bộ nhớ bằng tiến trình riêng — documents/CONTEXT.md §4.9."""

import chess
import pytest

from tournament.process_player import ProcessPlayer, memory_usage
from tournament.round_robin import RoundRobinRunner


def test_memory_usage_reports_current_and_peak():
    current, peak = memory_usage()
    assert 0 < current <= peak


def test_process_player_plays_and_reports_memory_after_closing():
    player = ProcessPlayer("bench_random", {"seed": 1})
    board = chess.Board()
    board.push_uci("e2e4")
    player.reset()
    move = player.select_move(board)
    assert move in board.legal_moves
    assert player.measured_think_time_s is not None and player.measured_think_time_s >= 0
    used = player.close()
    assert used is not None and used >= 0
    assert not player._process.is_alive()


def test_unknown_bot_fails_in_the_constructor():
    with pytest.raises(RuntimeError):
        ProcessPlayer("does_not_exist")


def test_tournament_measures_memory_per_game_with_real_processes():
    runner = RoundRobinRunner(
        ["bench_random", "bench_alphabeta_material"],
        matches_per_pair=1,
        max_plies=6,
        random_opening_plies=0,
        depth=1,
        measure_memory=True,
    )
    result = runner.play()
    assert result.games_played == 2
    assert not result.errors
    assert all(row.memory_mb > 0 for row in result.standings)


def test_injected_bot_factories_never_use_processes():
    runner = RoundRobinRunner(
        ["a", "b"], matches_per_pair=1, create_bot=lambda *a: None, measure_memory=True
    )
    assert runner._measure_memory is False
