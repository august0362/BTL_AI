"""Tactical safety, adversarial backup and resource limits for the new heuristic."""

import gc
import random
import tracemalloc

import chess
import pytest

from ai.mcts.bot import MctsBot
from ai.mcts.evaluation import positional_score, score_to_reward
from ai.mcts.leaf import MATE, LeafEvaluator, LeafTimeout
from ai.mcts.node import Node, backup_replies
from ai.mcts.search import SearchConfig, search


def oracle(board: chess.Board, depth: int) -> float:
    """Independent complete minimax for small positions without captures at the horizon."""
    if depth == 0:
        return positional_score(board) * (1 if board.turn else -1)
    values = []
    for move in list(board.legal_moves):
        board.push(move)
        try:
            values.append(-oracle(board, depth - 1))
        finally:
            board.pop()
    return max(values)


@pytest.mark.parametrize("black", [False, True])
def test_leaf_matches_independent_minimax_when_no_exchanges_are_possible(black: bool) -> None:
    board = chess.Board("7k/7p/8/8/8/8/P7/K7 w - - 0 1")
    if black:
        board = board.mirror()
    expected = oracle(board, 2) * (1 if board.turn else -1)
    before = board.fen(), list(board.move_stack)
    assert LeafEvaluator(2).evaluate(board) == expected
    assert (board.fen(), board.move_stack) == before


def test_exchange_check_rejects_a_poisoned_pawn_capture() -> None:
    board = chess.Board("r5k1/8/8/8/8/8/p7/R3K3 w - - 0 1")
    board.push_uci("a1a2")
    before = board.fen(), list(board.move_stack)
    assert LeafEvaluator(0).evaluate(board) < positional_score(board) - 350
    assert (board.fen(), board.move_stack) == before


def test_check_evasions_include_quiet_king_moves() -> None:
    board = chess.Board("4r1k1/8/8/8/8/8/8/4K3 w - - 0 1")
    assert board.is_check()
    assert not any(board.is_capture(m) for m in board.legal_moves)
    assert LeafEvaluator(0).evaluate(board) == oracle(board, 1)


def test_checkmate_precedes_the_fifty_move_draw() -> None:
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 100 1")
    assert LeafEvaluator(2).evaluate(board) == MATE


def test_leaf_honors_actual_repetition_history() -> None:
    board = chess.Board()
    for uci in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
        board.push_uci(uci)
    assert LeafEvaluator(2).evaluate(board) == 0


def test_timeout_restores_every_pushed_move() -> None:
    calls = 0

    def clock() -> float:
        nonlocal calls
        calls += 1
        return 0 if calls < 2 else 2

    board = chess.Board()
    before = board.fen(), list(board.move_stack)
    with pytest.raises(LeafTimeout):
        LeafEvaluator(2, deadline=1, clock=clock).evaluate(board)
    assert (board.fen(), board.move_stack) == before


def test_opponents_best_reply_beats_an_optimistic_sample_average() -> None:
    root = Node(chess.BLACK, [], visits=20)
    trap = Node(chess.WHITE, [], visits=10, total_reward=9, reply_reward=0.1)
    safe = Node(chess.WHITE, [], visits=10, total_reward=6, reply_reward=0.6)
    root.children = [trap, safe]
    assert root.select_child(0) is trap
    assert root.select_heuristic_child(0) is safe


def test_untried_replies_do_not_erase_a_known_tactical_risk() -> None:
    parent = Node(chess.WHITE, [chess.Move.from_uci("a7a6")], leaf_reward=0.2)
    child = Node(chess.BLACK, [], parent=parent)
    parent.children = [child]
    backup_replies(child, 0.9)
    assert parent.reply_reward == pytest.approx(0.2)


def test_pure_mode_never_calls_the_leaf_heuristic(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Pure MCTS called the new heuristic")

    monkeypatch.setattr(LeafEvaluator, "evaluate", forbidden)
    bot = MctsBot(
        {"use_heuristics": False, "simulations": 10, "rollout_max_plies": 0, "max_think_time_s": 0}
    )
    assert bot.select_move(chess.Board()) in chess.Board().legal_moves
    assert bot.last_search_info["algorithm"] == "pure_mcts_uct"
    assert bot.last_search_info["leaf_nodes"] == 0


def test_tree_node_limit_is_respected() -> None:
    result = search(
        chess.Board(),
        SearchConfig(simulations=1000, max_think_time_s=0, max_tree_nodes=9, leaf_depth=0),
        random.Random(0),
    )
    assert result.info["nodes"] == 9
    assert result.move in chess.Board().legal_moves


def test_repeated_searches_leave_no_trees_for_cyclic_gc() -> None:
    bot = MctsBot({"seed": 0, "simulations": 20, "max_think_time_s": 0, "leaf_depth": 0})
    board = chess.Board()
    bot.select_move(board)
    enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        before, _ = tracemalloc.get_traced_memory()
        for _ in range(30):
            bot.select_move(board)
        after, _ = tracemalloc.get_traced_memory()
        assert after - before < 500_000
    finally:
        tracemalloc.stop()
        if enabled:
            gc.enable()


def test_estimates_never_claim_a_proven_win_and_remain_color_symmetric() -> None:
    for cp in (0, 100, 1000, MATE):
        assert 0 < score_to_reward(cp) < 1
        assert score_to_reward(cp) + score_to_reward(-cp) == pytest.approx(1)


@pytest.mark.parametrize("config", [{"leaf_depth": -1}, {"leaf_depth": 3}, {"max_tree_nodes": 1}])
def test_invalid_new_limits_are_rejected(config: dict) -> None:
    with pytest.raises(ValueError, match="mcts:"):
        MctsBot(config)
