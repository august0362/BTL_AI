"""Shared random baseline bot plus the material evaluation reused by Benchmark 2."""

from __future__ import annotations

import random

import chess

from ai.base_bot import BaseBot

# Bảng giá trị cơ bản của các quân cờ (Material values)
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def evaluate(board: chess.Board) -> int:
    """Đánh giá thế trận: dương ưu thế cho Trắng, âm ưu thế cho Đen."""
    if board.is_checkmate():
        # Nếu bên nào bị chiếu hết thì thua điểm cực lớn
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            value = PIECE_VALUES[piece.piece_type]
            score += value if piece.color == chess.WHITE else -value
    return score


class RandomBaselineBot(BaseBot):
    """Placeholder for unfinished bots: pick a seeded uniformly random legal move."""

    is_baseline = True

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._rng = random.Random(self.config.get("seed"))

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a uniformly selected legal move."""
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        self.last_search_info = {}
        return self._rng.choice(moves)
