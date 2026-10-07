"""Đặc tả các bot benchmark cho giải xếp hạng AI — documents/CONTEXT.md §4.2."""

import chess
import pytest

from ai import registry
from ai.benchmarks import evaluation, search
from ai.benchmarks.bot import MAX_DEPTH, BenchmarkAlphaBetaCustomBot, resolve_depth

BENCHMARK_IDS = list(registry.BENCHMARK_BOTS)
FAST = {"fast_mode": True, "depth": 1, "seed": 0}

POSITIONS = {
    "start": chess.STARTING_FEN,
    "middlegame": "r1bqkbnr/pppp1ppp/2n5/4p3/4B3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "black_to_move": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "promotion": "8/P6k/8/8/8/8/8/K7 w - - 0 1",
}
ONLY_MOVE_FEN = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
CENTRAL_KNIGHT_FEN = "rnbqkbnr/pppppppp/8/8/3N4/8/PPPPPPPP/RNBQKB1R w KQkq - 0 1"
CAPTURE_FEN = "4k3/8/8/3p4/4P3/8/8/4K3 w - - 0 1"


@pytest.mark.parametrize("bot_id", BENCHMARK_IDS)
@pytest.mark.parametrize("name", list(POSITIONS))
def test_benchmarks_return_legal_moves_without_mutating(bot_id, name):
    bot = registry.create_bot(bot_id, dict(FAST))
    board = chess.Board(POSITIONS[name])
    before = (board.fen(), len(board.move_stack))
    move = bot.select_move(board)
    assert move in chess.Board(POSITIONS[name]).legal_moves
    assert (board.fen(), len(board.move_stack)) == before
    assert isinstance(bot.last_search_info, dict)


@pytest.mark.parametrize("bot_id", BENCHMARK_IDS)
def test_benchmarks_find_the_only_legal_move(bot_id):
    bot = registry.create_bot(bot_id, dict(FAST))
    assert bot.select_move(chess.Board(ONLY_MOVE_FEN)) == chess.Move.from_uci("e1e2")


@pytest.mark.parametrize("bot_id", BENCHMARK_IDS)
def test_benchmarks_are_deterministic(bot_id):
    first = registry.create_bot(bot_id, {"depth": 2, "seed": 7})
    second = registry.create_bot(bot_id, {"depth": 2, "seed": 7})
    moves_first = [first.select_move(chess.Board()).uci() for _ in range(3)]
    moves_second = [second.select_move(chess.Board()).uci() for _ in range(3)]
    assert moves_first == moves_second


def test_seeded_random_benchmark_repeats_its_move_sequence():
    first = registry.create_bot("bench_random", {"seed": 17})
    second = registry.create_bot("bench_random", {"seed": 17})
    first_board, second_board = chess.Board(), chess.Board()
    for _ in range(12):
        move = first.select_move(first_board)
        other = second.select_move(second_board)
        assert move.uci() == other.uci()
        first_board.push(move)
        second_board.push(other)


def test_alpha_beta_benchmark_reports_configured_depth():
    bot = registry.create_bot("bench_alphabeta3", {"depth": 2})
    bot.select_move(chess.Board(POSITIONS["middlegame"]))
    assert bot.last_search_info["depth"] == 2
    assert bot.last_search_info["nodes"] > 0


@pytest.mark.parametrize("depth", [1, 2, 3])
def test_transposition_table_matches_plain_search(depth):
    board = chess.Board(POSITIONS["middlegame"])
    evaluator = evaluation.build_evaluator("material")
    plain = search.alpha_beta(board, depth, evaluator)
    with_tt = search.alpha_beta_tt(board, depth, evaluator)
    assert with_tt.score == plain.score
    assert with_tt.move in board.legal_moves


def test_move_ordering_puts_captures_first():
    board = chess.Board(CAPTURE_FEN)
    ordered = search.order_moves(board)
    assert board.is_capture(ordered[0])


def test_positional_evaluator_uses_more_than_material():
    board = chess.Board(CENTRAL_KNIGHT_FEN)
    assert evaluation.material_evaluator(board) == 0
    assert evaluation.positional_evaluator(board) > 0


def test_unknown_evaluator_raises():
    with pytest.raises(ValueError):
        evaluation.build_evaluator("does_not_exist")


def test_custom_benchmark_uses_the_configured_evaluator():
    bot = BenchmarkAlphaBetaCustomBot({"depth": 1, "evaluator": "positional"})
    assert isinstance(bot, BenchmarkAlphaBetaCustomBot)
    assert bot.evaluator_name == "positional"
    assert bot.select_move(chess.Board()) in chess.Board().legal_moves


def test_resolve_depth_defaults_and_clamps():
    assert resolve_depth({"fast_mode": True}) == 1
    assert resolve_depth({}) == 3
    assert resolve_depth({"depth": 5}) == 5
    assert resolve_depth({"depth": MAX_DEPTH + 10}) == MAX_DEPTH
    assert resolve_depth({"depth": "not-a-number"}) == 3


def test_search_benchmark_reset_clears_search_info():
    bot = registry.create_bot("bench_alphabeta_tt", {"depth": 1})
    bot.select_move(chess.Board())
    bot.reset()
    assert bot.last_search_info == {}


def test_resolve_time_limit_parsing():
    from ai.benchmarks.bot import resolve_time_limit

    assert resolve_time_limit({}) is None
    assert resolve_time_limit({"max_think_time_s": 0}) is None
    assert resolve_time_limit({"max_think_time_s": -2}) is None
    assert resolve_time_limit({"max_think_time_s": 0.5}) == 0.5
    assert resolve_time_limit({"max_think_time_s": "0.25"}) == 0.25
    assert resolve_time_limit({"max_think_time_s": "bad"}) is None


def test_iterative_search_reaches_max_depth_without_a_limit():
    board = chess.Board(POSITIONS["middlegame"])
    evaluator = evaluation.build_evaluator("material")
    plain = search.alpha_beta(board, 3, evaluator)
    iterated = search.alpha_beta_iterative(board, 3, evaluator)
    assert iterated.depth == 3
    assert iterated.move == plain.move
    assert iterated.score == plain.score


def test_iterative_search_stops_within_the_time_budget():
    import time

    board = chess.Board(POSITIONS["middlegame"])
    evaluator = evaluation.build_evaluator("material")
    started = time.perf_counter()
    result = search.alpha_beta_iterative(board, 20, evaluator, time_limit_s=0.05)
    elapsed = time.perf_counter() - started
    assert result.move in board.legal_moves
    assert 1 <= result.depth < 20
    assert elapsed < 5.0


def test_iterative_search_with_a_tiny_budget_still_returns_a_legal_move():
    board = chess.Board(POSITIONS["middlegame"])
    evaluator = evaluation.build_evaluator("material")
    result = search.alpha_beta_iterative(board, 20, evaluator, time_limit_s=1e-9)
    assert result.move in board.legal_moves


def test_search_benchmark_bot_exposes_the_configured_budget():
    bot = registry.create_bot("bench_alphabeta3", {"depth": 2, "max_think_time_s": 0.5})
    bot.select_move(chess.Board())
    assert bot.time_limit_s == 0.5
    assert bot.last_search_info["depth"] == 2
