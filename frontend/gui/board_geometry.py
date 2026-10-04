"""Display-independent mapping between board squares and canvas coordinates."""

from __future__ import annotations

import chess

BOARD_SIZE = 640
SQUARE_SIZE = 80


def square_at(x: float, y: float, flipped: bool = False) -> chess.Square | None:
    """Return the square at a canvas point, or None when the point is off the board."""
    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        return None

    file_index = int(x // SQUARE_SIZE)
    row_index = int(y // SQUARE_SIZE)
    if flipped:
        return chess.square(7 - file_index, row_index)
    return chess.square(file_index, 7 - row_index)


def square_origin(square: chess.Square, flipped: bool = False) -> tuple[int, int]:
    """Return the canvas origin of a square."""
    file_index = chess.square_file(square)
    rank_index = chess.square_rank(square)
    if flipped:
        return (7 - file_index) * SQUARE_SIZE, rank_index * SQUARE_SIZE
    return file_index * SQUARE_SIZE, (7 - rank_index) * SQUARE_SIZE
