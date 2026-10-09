"""Đặc tả Benchmark 6 (4 profile) và Benchmark 7 — documents/CONTEXT.md §4.9.2."""

import random
import time

import chess
import pytest

from ai import registry
from ai.benchmarks_extension.bench6.evaluation import Evaluator6, pack, unpack
from ai.benchmarks_extension.bench6.profiles import PROFILES6
from ai.benchmarks_extension.bench6.search import BOOK_LINES, EXACT, Engine6, _build_book
from ai.benchmarks_extension.bench7.evaluation import Evaluator6 as Evaluator7
from ai.benchmarks_extension.bench7.profile import B7

B6_IDS = ["bench6_gpt", "bench6_gemini", "bench6_grok", "bench6_deepseek", "bench7"]
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


def test_all_profiles_are_registered_benchmarks():
    assert all(bot_id in registry.BENCHMARK_BOTS for bot_id in B6_IDS)
    for bot_id in B6_IDS:
        bot = registry.create_bot(bot_id, {"depth": 1})
        assert bot.bot_id == bot_id
        assert bot.display_name.startswith(("Benchmark 6", "Benchmark 7"))


def test_pack_round_trip():
    for mg, eg in ((0, 0), (37, -12), (-900, 4000), (-3, -7)):
        assert unpack(pack(mg, eg)) == (mg, eg)
        assert unpack(pack(mg, eg) - pack(1, 1)) == (mg - 1, eg - 1)


@pytest.mark.parametrize("name", sorted(PROFILES6))
def test_evaluation_is_colour_symmetric(name):
    evaluate = Evaluator6(PROFILES6[name].evaluation)
    for board in _random_boards(6, 120):
        assert evaluate(board) == evaluate(board.mirror())


@pytest.mark.parametrize("name", ["gpt", "gemini"])
def test_incremental_pst_matches_full_recomputation(name):
    profile = PROFILES6[name]
    engine = Engine6(profile.search, Evaluator6(profile.evaluation))
    engine._ensure_tables()
    rng = random.Random(9)
    for start in ("", "r3k2r/pPpp1ppp/8/4pP2/8/8/PPPPP1PP/R3K2R w KQkq e6 0 1"):
        board = chess.Board(start) if start else chess.Board()
        engine.board = board
        engine.packed = engine.evaluator.pst_sum(board)
        engine._packed_stack = []
        for ply in range(60):
            moves = list(board.legal_moves)
            if not moves:
                break
            engine._push(rng.choice(moves), min(ply, 100))
            assert engine.packed == engine.evaluator.pst_sum(board)
        while engine._packed_stack:
            engine._pop()
            assert engine.packed == engine.evaluator.pst_sum(board)


def test_hand_written_book_is_legal():
    book = _build_book()
    assert len(book) == len(BOOK_LINES)
    for line, replies in BOOK_LINES:
        board = chess.Board()
        for san in line.split():
            board.push_san(san)
        for san in replies:
            assert board.parse_san(san) in board.legal_moves


def test_bucketed_tt_keeps_the_deeper_entry():
    profile = PROFILES6["deepseek"]
    engine = Engine6(profile.search, Evaluator6(profile.evaluation))
    engine._ensure_tables()
    move = chess.Move.from_uci("e2e4")
    engine._tt_store(12345, 6, 40, EXACT, move, None, 0)
    assert engine._tt_probe(12345)[1:5] == (6, 40, EXACT, move)
    engine._tt_store(12345, 2, 10, 1, None, None, 0)  # shallower bound: kept the deep one
    assert engine._tt_probe(12345)[1] == 6


@pytest.mark.parametrize("bot_id", B6_IDS)
def test_finds_mate_in_one_and_two(bot_id):
    bot = registry.create_bot(bot_id, {"depth": 4, "max_think_time_s": 5})
    board = chess.Board(MATE_IN_ONE)
    board.push(bot.select_move(board))
    assert board.is_checkmate()

    board = chess.Board(MATE_IN_TWO)
    assert bot.select_move(board) == chess.Move.from_uci("e2e8")
    assert bot.last_search_info["eval"] >= 90_000


@pytest.mark.parametrize("bot_id", B6_IDS)
def test_respects_the_time_budget(bot_id):
    bot = registry.create_bot(bot_id, {"max_think_time_s": 0.3})
    board = chess.Board(MIDDLEGAME)
    started = time.perf_counter()
    move = bot.select_move(board)
    assert move in board.legal_moves
    assert time.perf_counter() - started < 0.45
    assert bot.last_search_info["depth"] >= 1


@pytest.mark.parametrize("bot_id", ["bench6_gpt", "bench6_deepseek", "bench7"])
def test_winning_side_does_not_repeat(bot_id):
    board = chess.Board("4k3/8/8/8/8/8/4K3/R7 w - - 0 1")
    for uci in ("a1a2", "e8d8", "a2a1", "d8e8"):
        board.push_uci(uci)
    bot = registry.create_bot(bot_id, {"max_think_time_s": 0.5})
    assert bot.select_move(board) != chess.Move.from_uci("a1a2")


def test_benchmark7_evaluation_is_colour_symmetric():
    evaluate = Evaluator7(B7.evaluation)
    for board in _random_boards(7, 120):
        assert evaluate(board) == evaluate(board.mirror())
