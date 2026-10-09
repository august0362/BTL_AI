"""Đặc tả Benchmark 5 (5 profile PVS dùng hết thời gian) — documents/CONTEXT.md §4.9."""

import random
import time

import chess
import pytest

from ai import registry
from ai.benchmarks_extension.bench5.evaluation import Evaluator5
from ai.benchmarks_extension.bench5.profiles import PROFILES
from ai.benchmarks_extension.bench5.search import see

B5_IDS = ["bench5_gpt", "bench5_gemini", "bench5_deepseek", "bench5_grok", "bench5_hybrid"]
MATE_IN_ONE = "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4"
MATE_IN_TWO = "r5k1/5ppp/8/8/8/8/4RPPP/4R1K1 w - - 0 1"  # 1.Re8+ Rxe8 2.Rxe8#
MIDDLEGAME = "r2q1rk1/1b1nbppp/p2ppn2/1p6/3NP3/1BN1BP2/PPPQ2PP/2KR3R w - - 0 12"


def test_all_five_profiles_are_registered_benchmarks():
    assert all(bot_id in registry.BENCHMARK_BOTS for bot_id in B5_IDS)
    assert sorted(PROFILES) == sorted(["gpt", "gemini", "deepseek", "grok", "hybrid"])
    for bot_id in B5_IDS:
        bot = registry.create_bot(bot_id, {"depth": 1})
        assert bot.bot_id == bot_id
        assert bot.display_name.startswith("Benchmark 5")


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_evaluation_is_colour_symmetric(name):
    evaluate = Evaluator5(PROFILES[name].evaluation)
    rng = random.Random(5)
    for _ in range(120):
        board = chess.Board()
        for _ in range(rng.randint(0, 70)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        assert evaluate(board) == evaluate(board.mirror())


def test_static_exchange_evaluation():
    defended_knight = chess.Board("4k3/8/2p5/3n4/4P3/8/8/4K3 w - - 0 1")
    assert see(defended_knight, chess.Move.from_uci("e4d5")) == 320 - 100
    defended_pawn = chess.Board("4k3/8/2p5/3p4/8/8/3Q4/4K3 w - - 0 1")
    assert see(defended_pawn, chess.Move.from_uci("d2d5")) == 100 - 900


@pytest.mark.parametrize("bot_id", B5_IDS)
def test_finds_mate_in_one_and_two(bot_id):
    bot = registry.create_bot(bot_id, {"depth": 4, "max_think_time_s": 5})
    board = chess.Board(MATE_IN_ONE)
    board.push(bot.select_move(board))
    assert board.is_checkmate()

    board = chess.Board(MATE_IN_TWO)
    assert bot.select_move(board) == chess.Move.from_uci("e2e8")
    assert bot.last_search_info["eval"] >= 90_000


@pytest.mark.parametrize("bot_id", B5_IDS)
def test_respects_the_time_budget(bot_id):
    bot = registry.create_bot(bot_id, {"max_think_time_s": 0.3})
    board = chess.Board(MIDDLEGAME)
    started = time.perf_counter()
    move = bot.select_move(board)
    assert move in board.legal_moves
    assert time.perf_counter() - started < 0.6
    assert bot.last_search_info["depth"] >= 1


@pytest.mark.parametrize("bot_id", ["bench5_gpt", "bench5_deepseek", "bench5_hybrid"])
def test_winning_side_does_not_repeat(bot_id):
    board = chess.Board("4k3/8/8/8/8/8/4K3/R7 w - - 0 1")
    for uci in ("a1a2", "e8d8", "a2a1", "d8e8"):
        board.push_uci(uci)
    bot = registry.create_bot(bot_id, {"max_think_time_s": 0.5})
    assert bot.select_move(board) != chess.Move.from_uci("a1a2")
