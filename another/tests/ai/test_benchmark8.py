"""Đặc tả Benchmark 8 "Luna" — documents/CONTEXT.md §4.9.3."""

import random
import time
from dataclasses import replace

import chess

from ai import registry
from ai.bench8.bot import Benchmark8LunaBot, resolve_ply_limit
from ai.bench8.evaluation import Evaluator8
from ai.bench8.profile import LUNA, TOURNAMENT_PLY_LIMIT
from ai.bench8.search import Engine8, Verify8, see, see_ge

MATE_IN_ONE = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
MATE_IN_TWO = "r5k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - - 0 1"  # 1.Re8+ Rxe8 2.Rxe8#
MIDDLEGAME = "r2q1rk1/1b1nbppp/p2ppn2/1p6/3NP3/1BN1BP2/PPPQ2PP/2KR3R w - - 0 12"


def _random_boards(seed: int, count: int) -> list[chess.Board]:
    rng = random.Random(seed)
    boards = []
    for _ in range(count):
        board = chess.Board()
        for _ in range(rng.randint(0, 80)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        boards.append(board)
    return boards


def _engine(**changes) -> Engine8:
    search = replace(LUNA.search, book=False, **changes)
    return Engine8(search, Evaluator8(LUNA.evaluation))


def test_luna_is_a_level_8_benchmark():
    assert registry.BENCHMARK_LEVELS["bench8_luna"] == 8
    bot = registry.create_bot("bench8_luna", {"depth": 1})
    assert isinstance(bot, Benchmark8LunaBot)
    assert bot.display_name.startswith("Benchmark 8")
    assert "bench8_luna" not in registry.list_bots(include_benchmarks=True, max_benchmark_level=7)
    assert "bench8_luna" in registry.list_bots(include_benchmarks=True, max_benchmark_level=8)


def test_threshold_see_matches_the_full_swap_list():
    for board in _random_boards(81, 60):
        for move in board.legal_moves:
            value = see(board, move)
            for threshold in (-300, -100, -1, 0, 1, 100, 300):
                assert see_ge(board, move, threshold) == (value >= threshold)


def test_fast_see_does_not_change_the_search():
    board = chess.Board(MIDDLEGAME)
    fast = _engine(fast_see=True).search(board.copy(), None, 5)
    slow = _engine(fast_see=False).search(board.copy(), None, 5)
    assert (fast.move, fast.score, fast.nodes) == (slow.move, slow.score, slow.nodes)


def test_evaluation_is_colour_symmetric():
    evaluate = Evaluator8(replace(LUNA.evaluation, kpk=150))
    boards = _random_boards(8, 120) + [
        chess.Board("8/8/3K4/8/3P4/8/8/6k1 w - - 0 1"),
        chess.Board("8/8/3k4/8/3P4/8/8/6K1 b - - 0 1"),
    ]
    for board in boards:
        assert evaluate(board) == evaluate(board.mirror())


def test_kpk_key_square_and_defender_in_front():
    evaluate = Evaluator8(replace(LUNA.evaluation, kpk=150))
    assert evaluate(chess.Board("8/8/3K4/8/3P4/8/8/6k1 w - - 0 1")) >= 200
    assert abs(evaluate(chess.Board("8/8/3k4/8/3P4/8/8/6K1 w - - 0 1"))) < 50


def test_positions_past_the_ply_limit_are_draws():
    board = chess.Board("6k1/8/8/8/8/8/8/Q5K1 w - - 0 1")  # a queen up, game ends next ply
    assert abs(_engine(ply_limit=1).search(board.copy(), None, 3).score) <= 50
    assert _engine(ply_limit=0).search(board.copy(), None, 3).score > 500


def test_ply_limit_from_config():
    assert resolve_ply_limit({}, TOURNAMENT_PLY_LIMIT) == 150
    assert resolve_ply_limit({"max_plies": 300}, 150) == 300
    assert resolve_ply_limit({"max_plies": "x"}, 150) == 150


def test_verification_and_guard_keep_mates_and_legality():
    for changes in ({"verify": Verify8(tactical_only=False)}, {"push_guard": True}):
        engine = _engine(**changes)
        assert engine.search(chess.Board(MATE_IN_TWO), None, 5).move == chess.Move.from_uci("e2e8")
        board = chess.Board(MIDDLEGAME)
        assert engine.search(board, None, 4).move in board.legal_moves


def test_finds_mates():
    bot = Benchmark8LunaBot({"max_think_time_s": 1.0})
    assert bot.select_move(chess.Board(MATE_IN_ONE)) == chess.Move.from_uci("h5f7")
    assert bot.select_move(chess.Board(MATE_IN_TWO)) == chess.Move.from_uci("e2e8")


def test_time_limit_and_board_restored():
    bot = Benchmark8LunaBot({"max_think_time_s": 0.3})
    board = chess.Board(MIDDLEGAME)
    before = board.fen()
    started = time.perf_counter()
    move = bot.select_move(board)
    assert time.perf_counter() - started < 0.5
    assert board.fen() == before
    assert move in board.legal_moves


def test_fast_mode_and_independent_instances():
    first = Benchmark8LunaBot({"fast_mode": True})
    second = Benchmark8LunaBot({"fast_mode": True})
    assert first.max_depth == 2
    board = chess.Board()
    for _ in range(6):
        bot = first if board.turn == chess.WHITE else second
        move = bot.select_move(board)
        assert move in board.legal_moves
        board.push(move)
    assert first._engine is not second._engine
