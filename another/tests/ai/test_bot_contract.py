"""Test hợp đồng — MỌI bot trong registry phải qua. documents/CONTEXT.md §4.1.

Bot chưa triển khai (raise BotUnavailableError) sẽ được bỏ qua.
Bot nhận config CONTRACT_CONFIG: nên dùng tìm kiếm nhỏ khi fast_mode=True để CI chạy nhanh.
"""

import chess
import pytest

from tests._helpers import require_module

registry = require_module("ai.registry")
base = require_module("ai.base_bot")

CONTRACT_CONFIG = {"fast_mode": True, "allow_random_init": True, "seed": 0}

POSITIONS = {
    "start": chess.STARTING_FEN,
    "black_to_move": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "middlegame": "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "promotion": "8/P6k/8/8/8/8/8/K7 w - - 0 1",
    "en_passant": "4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2",
    "castling": "r3k2r/pppppppp/8/8/8/8/PPPPPPPP/R3K2R w KQkq - 0 1",
    "endgame_kqk": "8/8/8/4k3/8/8/8/3QK3 w - - 0 1",
}
ONLY_MOVE_FEN = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"  # đang bị chiếu, chỉ có Kxe2
ALL_BOTS = registry.list_bots(include_debug=True)


def make(bot_id):
    try:
        return registry.create_bot(bot_id, dict(CONTRACT_CONFIG))
    except base.BotUnavailableError as e:
        pytest.skip(f"{bot_id}: {e}")


@pytest.fixture(params=ALL_BOTS)
def bot_id(request):
    return request.param


def test_identity(bot_id):
    bot = make(bot_id)
    assert isinstance(bot, base.BaseBot)
    assert bot.bot_id == bot_id
    assert isinstance(bot.display_name, str) and bot.display_name


@pytest.mark.parametrize("name", list(POSITIONS))
def test_returns_legal_move_without_mutating(bot_id, name):
    bot = make(bot_id)
    board = chess.Board(POSITIONS[name])
    before = (board.fen(), len(board.move_stack))
    move = bot.select_move(board)
    assert isinstance(move, chess.Move)
    assert move in chess.Board(POSITIONS[name]).legal_moves
    assert (board.fen(), len(board.move_stack)) == before, "bot đã sửa board đầu vào"
    assert isinstance(bot.last_search_info, dict)


def test_finds_only_legal_move(bot_id):
    bot = make(bot_id)
    assert bot.select_move(chess.Board(ONLY_MOVE_FEN)) == chess.Move.from_uci("e1e2")


def test_reset_then_move(bot_id):
    bot = make(bot_id)
    bot.select_move(chess.Board())
    bot.reset()
    assert bot.select_move(chess.Board()) in chess.Board().legal_moves


def test_two_instances_self_play(bot_id):
    # Hai instance cùng loại đấu nhau (cần cho Bot vs Bot trùng bot).
    white, black = make(bot_id), make(bot_id)
    board = chess.Board()
    for _ in range(12):
        if board.is_game_over():
            break
        player = white if board.turn == chess.WHITE else black
        move = player.select_move(board.copy())
        assert move in board.legal_moves
        board.push(move)
