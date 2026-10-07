"""Tests for Benchmark 3 (quiescence) and Benchmark 4 (advanced evaluation)."""

import chess

from ai import registry
from ai.benchmarks import evaluation, search


def test_benchmark3_and_4_use_their_default_evaluators() -> None:
    assert registry.create_bot("bench_alphabeta_tt", {"depth": 1}).evaluator_name == "pst"
    assert registry.create_bot("bench_alphabeta_custom", {"depth": 1}).evaluator_name == "advanced"


def test_quiescence_sees_the_recapture_beyond_the_horizon() -> None:
    # Qxd5 wins a pawn at depth 1, but the c6 pawn recaptures the queen.
    board = chess.Board("4k3/8/2p5/3p4/8/8/8/3QK3 w - - 0 1")
    evaluator = evaluation.build_evaluator("pst")
    plain = search.alpha_beta_iterative(board, 1, evaluator)
    quiet = search.alpha_beta_iterative(board, 1, evaluator, quiescence=True)
    assert plain.move == chess.Move.from_uci("d1d5")
    assert quiet.move != chess.Move.from_uci("d1d5")


def test_advanced_penalises_doubled_isolated_pawns() -> None:
    healthy = chess.Board("4k3/pppp4/8/8/8/8/PPPP4/4K3 w - - 0 1")
    broken = chess.Board("4k3/pppp4/8/8/8/P7/P1P1P3/4K3 w - - 0 1")
    assert evaluation.advanced_evaluator(healthy) > evaluation.advanced_evaluator(broken)


def test_advanced_rewards_a_passed_pawn() -> None:
    passed = chess.Board("4k3/7p/8/8/P7/8/8/4K3 w - - 0 1")
    blocked = chess.Board("4k3/p7/8/8/P7/8/8/4K3 w - - 0 1")
    gap = evaluation.advanced_evaluator(passed) - evaluation.pst_evaluator(passed)
    assert gap > evaluation.advanced_evaluator(blocked) - evaluation.pst_evaluator(blocked)


def test_advanced_rewards_the_bishop_pair() -> None:
    pair = chess.Board("4k3/pppp4/8/8/8/8/PPPP4/2B1KB2 w - - 0 1")
    single = chess.Board("4k3/pppp4/8/8/8/8/PPPP4/2N1KB2 w - - 0 1")
    gap_pair = evaluation.advanced_evaluator(pair) - evaluation.pst_evaluator(pair)
    gap_single = evaluation.advanced_evaluator(single) - evaluation.pst_evaluator(single)
    assert gap_pair > gap_single


def test_advanced_rewards_a_rook_on_an_open_file() -> None:
    open_file = chess.Board("4k3/1ppp4/8/8/8/8/1PPP4/R3K3 w - - 0 1")
    closed_file = chess.Board("4k3/ppp5/8/8/8/8/PPP5/R3K3 w - - 0 1")
    gap_open = evaluation.advanced_evaluator(open_file) - evaluation.pst_evaluator(open_file)
    gap_closed = evaluation.advanced_evaluator(closed_file) - evaluation.pst_evaluator(closed_file)
    assert gap_open > gap_closed


def test_advanced_rewards_mobility() -> None:
    active = chess.Board("4k3/pppp4/8/8/3N4/8/PPPP4/4K3 w - - 0 1")
    cornered = chess.Board("4k3/pppp4/8/8/8/8/PPPP4/N3K3 w - - 0 1")
    gap_active = evaluation.advanced_evaluator(active) - evaluation.pst_evaluator(active)
    gap_cornered = evaluation.advanced_evaluator(cornered) - evaluation.pst_evaluator(cornered)
    assert gap_active > gap_cornered


def test_benchmark4_finds_a_back_rank_mate() -> None:
    bot = registry.create_bot("bench_alphabeta_custom", {"depth": 3})
    board = chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
    assert bot.select_move(board) == chess.Move.from_uci("a1a8")
