import chess
import numpy as np

from ai.deep_rl.encoding import (
    action_to_move,
    encode_afterstates,
    encode_board,
    legal_action_mask,
    move_to_action,
)


def test_board_encoding_start_and_black_perspective() -> None:
    board = chess.Board()
    encoded = encode_board(board)
    assert encoded.shape == (18, 8, 8)
    assert encoded.dtype == np.float32
    assert encoded[0, 6].sum() == 8
    assert encoded[6, 1].sum() == 8

    board.turn = chess.BLACK
    black_view = encode_board(board)
    assert black_view[0, 6].sum() == 8
    assert black_view[6, 1].sum() == 8


def test_afterstates_are_from_movers_perspective() -> None:
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")
    afterstate = encode_afterstates(board, [move])
    assert afterstate.shape == (1, 18, 8, 8)
    assert afterstate[0, 0, 4, 4] == 1
    assert board.piece_at(chess.E2) == chess.Piece(chess.PAWN, chess.WHITE)


def test_action_round_trip_for_legal_moves_and_promotions() -> None:
    boards = [
        chess.Board(),
        chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"),
        chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1"),
        chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2"),
    ]
    for board in boards:
        for move in board.legal_moves:
            index = move_to_action(move, board.turn)
            decoded = action_to_move(index, board)
            assert decoded.from_square == move.from_square
            assert decoded.to_square == move.to_square
            if move.promotion:
                assert decoded.promotion == chess.QUEEN
            else:
                assert decoded == move


def test_legal_mask_contains_legal_actions_only() -> None:
    board = chess.Board()
    mask = legal_action_mask(board)
    assert mask.shape == (4096,)
    assert mask.dtype == np.bool_
    assert mask.sum() == board.legal_moves.count()
    for move in board.legal_moves:
        assert mask[move_to_action(move, board.turn)]
