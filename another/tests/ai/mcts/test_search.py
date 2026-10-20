"""Algorithm-level checks that a random baseline cannot satisfy."""

import math
import random

import chess
import pytest

from ai.mcts.evaluation import estimated_white_reward, positional_score
from ai.mcts.node import Node, backpropagate, robust_child
from ai.mcts.search import SearchConfig, expand, rollout, search, terminal_reward


def test_uct_matches_formula_and_prioritizes_unvisited() -> None:
    node = Node(chess.WHITE, [], visits=4, total_reward=3)
    assert node.uct(20, 1.4) == pytest.approx(0.75 + 1.4 * math.sqrt(math.log(20) / 4))
    assert Node(chess.BLACK, []).uct(0, 1.4) == math.inf
    assert node.uct(0, 1.4) == pytest.approx(0.75)


@pytest.mark.parametrize("white_reward", [0.0, 0.5, 1.0])
def test_backup_uses_each_previous_movers_perspective(white_reward: float) -> None:
    root = Node(chess.BLACK, [])
    white = Node(chess.WHITE, [], parent=root)
    black = Node(chess.BLACK, [], parent=white)
    backpropagate(black, white_reward)
    assert (root.visits, white.visits, black.visits) == (1, 1, 1)
    assert white.total_reward == white_reward
    assert black.total_reward == root.total_reward == 1 - white_reward


def test_selection_lets_black_maximize_blacks_reward() -> None:
    white = Node(chess.WHITE, [], visits=20)
    good_for_black = Node(chess.BLACK, [], visits=10, total_reward=8, parent=white)
    bad_for_black = Node(chess.BLACK, [], visits=10, total_reward=2, parent=white)
    white.children = [bad_for_black, good_for_black]
    assert white.select_child(1.4) is good_for_black


def test_final_choice_is_most_visited_not_highest_mean() -> None:
    root = Node(chess.BLACK, [])
    frequent = Node(chess.WHITE, [], visits=10, total_reward=6)
    lucky = Node(chess.WHITE, [], visits=1, total_reward=1)
    root.children = [lucky, frequent]
    assert robust_child(root) is frequent


def test_expansion_adds_exactly_one_distinct_move() -> None:
    board = chess.Board()
    root = Node(chess.BLACK, list(board.legal_moves))
    first = expand(root, board, random.Random(4), claim_draw=True)
    assert len(root.children) == 1
    assert len(root.untried_moves) == 19
    assert first.move not in root.untried_moves
    assert first.parent is root
    assert first.player_just_moved == chess.WHITE
    assert board.peek() == first.move


@pytest.mark.parametrize(
    ("fen", "expected"),
    [
        ("7k/6Q1/6K1/8/8/8/8/8 b - - 100 1", 1.0),
        ("8/8/8/8/8/6k1/6q1/7K w - - 100 1", 0.0),
        ("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1", 0.5),
        ("7k/8/6K1/8/8/8/8/8 w - - 0 1", 0.5),
    ],
)
def test_real_outcomes_and_mate_precedence(fen: str, expected: float) -> None:
    assert terminal_reward(chess.Board(fen)) == expected


def test_draw_requires_actual_repetition_not_a_possible_next_move() -> None:
    board = chess.Board()
    sequence = ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"]
    for uci in sequence:
        board.push_uci(uci)
    assert board.can_claim_threefold_repetition()
    assert terminal_reward(board) is None
    board.push_uci("f6g8")
    assert terminal_reward(board.copy(stack=True)) == 0.5
    assert terminal_reward(board.copy(stack=True), claim_draw=False) is None


def test_fifty_move_rule_uses_actual_halfmove_clock() -> None:
    board = chess.Board("7k/8/8/8/8/6K1/8/R7 w - - 99 1")
    assert terminal_reward(board) is None
    board.halfmove_clock = 100
    assert terminal_reward(board) == 0.5
    assert terminal_reward(board, claim_draw=False) is None


def test_pure_cutoff_is_neutral_and_does_not_call_heuristics(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        pytest.fail("Pure MCTS used a heuristic")

    monkeypatch.setattr("ai.mcts.search.estimated_white_reward", forbidden)
    monkeypatch.setattr("ai.mcts.search.move_priority", forbidden)
    cfg = SearchConfig(use_heuristics=False, rollout_max_plies=2, max_think_time_s=0)
    value, cutoff, plies = rollout(chess.Board(), cfg, random.Random(0))
    assert (value, cutoff, plies) == (0.5, True, 2)
    result = search(
        chess.Board(),
        SearchConfig(use_heuristics=False, rollout_max_plies=0, simulations=25, max_think_time_s=0),
        random.Random(0),
    )
    assert result.info["algorithm"] == "pure_mcts_uct"
    assert result.info["simulations"] == 25


def test_rollout_stops_at_real_mate_without_recording_a_cutoff() -> None:
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
    assert rollout(board, SearchConfig(), random.Random(0)) == (1.0, False, 0)


def test_assisted_cutoff_is_an_estimate_with_color_symmetry() -> None:
    board = chess.Board("7k/8/8/8/8/6K1/8/R7 w - - 0 1")
    assert positional_score(board) == -positional_score(board.mirror())
    assert estimated_white_reward(board) + estimated_white_reward(board.mirror()) == pytest.approx(
        1
    )
    reward, cutoff, _ = rollout(board, SearchConfig(rollout_max_plies=0), random.Random(0))
    assert cutoff
    assert 0.5 < reward < 1.0


def test_pure_search_discovers_mate_through_tree_statistics() -> None:
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    result = search(
        board,
        SearchConfig(
            simulations=1000, use_heuristics=False, rollout_max_plies=0, max_think_time_s=0
        ),
        random.Random(0),
    )
    board.push(result.move)
    assert board.is_checkmate()
    assert result.info["shortcut"] is None
    assert result.info["root_visits"] == result.info["simulations"] == 1000
    assert sum(row["visits"] for row in result.info["root_children"]) == 1000


def test_deadline_returns_a_legal_fallback_without_starting_a_simulation() -> None:
    result = search(
        chess.Board(),
        SearchConfig(max_think_time_s=1),
        random.Random(0),
        started=0,
        clock=lambda: 2.0,
    )
    assert result.move in chess.Board().legal_moves
    assert result.info["simulations"] == 0


def test_deadline_can_interrupt_a_long_rollout() -> None:
    ticks = iter([0.0, 0.1, 2.0])
    value, cutoff, plies = rollout(
        chess.Board(),
        SearchConfig(use_heuristics=False, rollout_max_plies=10000),
        random.Random(0),
        deadline=1,
        clock=lambda: next(ticks),
    )
    assert (value, cutoff, plies) == (0.5, True, 2)
