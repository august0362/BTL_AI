"""Tests for the Benchmark 2 piece-square evaluation and seeded tie-breaking."""

import chess

from ai import registry
from ai.benchmarks import evaluation


def test_pst_prefers_a_central_knight_over_a_corner_knight() -> None:
    central = chess.Board("4k3/p7/8/8/4N3/8/P7/4K3 b - - 0 1")
    corner = chess.Board("4k3/p7/8/8/8/8/P7/N3K3 b - - 0 1")
    # Black to move, so a better White knight means a lower score for the mover.
    assert evaluation.pst_evaluator(central) < evaluation.pst_evaluator(corner)


def test_pst_is_symmetric_at_the_start() -> None:
    assert evaluation.pst_evaluator(chess.Board()) == 0


def test_pst_scores_faster_mates_higher() -> None:
    board = chess.Board()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        board.push_uci(uci)
    slow = board.copy()
    slow.fullmove_number += 10  # ply() is derived from the move number
    assert evaluation.pst_evaluator(board) < 0
    assert evaluation.pst_evaluator(board) < evaluation.pst_evaluator(slow)


def test_benchmark2_uses_pst_and_repeats_with_the_same_seed() -> None:
    first = registry.create_bot("bench_alphabeta3", {"depth": 2, "seed": 3})
    second = registry.create_bot("bench_alphabeta3", {"depth": 2, "seed": 3})
    assert first.evaluator_name == "pst"
    board_a, board_b = chess.Board(), chess.Board()
    for _ in range(6):
        move = first.select_move(board_a)
        assert move == second.select_move(board_b)
        board_a.push(move)
        board_b.push(move)


def test_benchmark2_takes_a_free_queen() -> None:
    bot = registry.create_bot("bench_alphabeta3", {"depth": 2, "seed": 1})
    board = chess.Board("4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1")
    assert bot.select_move(board) == chess.Move.from_uci("e4d5")
