"""Material counting and evaluation helpers."""

import math

import chess

PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


def material_diff(board: chess.Board) -> int:
    """Return white's material total minus black's material total."""
    white = sum(
        value * len(board.pieces(piece_type, chess.WHITE))
        for piece_type, value in PIECE_VALUES.items()
    )
    black = sum(
        value * len(board.pieces(piece_type, chess.BLACK))
        for piece_type, value in PIECE_VALUES.items()
    )
    return white - black


def eval_bar_value(board: chess.Board, scale: float = 8.0) -> float:
    """Return a bounded material evaluation from white's perspective."""
    return math.tanh(material_diff(board) / scale)
