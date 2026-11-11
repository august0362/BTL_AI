"""4672-action move encoding from the side to move's point of view.

``action = from_square * 73 + move_type``: 56 queen moves, 8 knight jumps,
and 9 underpromotions. Black mirrors ranks, matching ``features.encode``.
"""

from __future__ import annotations

import chess
import numpy as np

MOVE_TYPES = 73
ACTIONS = 64 * MOVE_TYPES

_QUEEN_DIRECTIONS = {
    (0, 1): 0,
    (1, 1): 1,
    (1, 0): 2,
    (1, -1): 3,
    (0, -1): 4,
    (-1, -1): 5,
    (-1, 0): 6,
    (-1, 1): 7,
}
_KNIGHT_JUMPS = {
    (1, 2): 0,
    (2, 1): 1,
    (2, -1): 2,
    (1, -2): 3,
    (-1, -2): 4,
    (-2, -1): 5,
    (-2, 1): 6,
    (-1, 2): 7,
}
_UNDERPROMOTIONS = {chess.KNIGHT: 0, chess.BISHOP: 1, chess.ROOK: 2}


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


def move_to_action(move: chess.Move, turn: chess.Color) -> int:
    """Return the action index in ``[0, 4672)`` for ``move`` played by ``turn``."""
    from_square, to_square = move.from_square, move.to_square
    if turn == chess.BLACK:
        from_square, to_square = from_square ^ 56, to_square ^ 56
    dx = chess.square_file(to_square) - chess.square_file(from_square)
    dy = chess.square_rank(to_square) - chess.square_rank(from_square)
    if move.promotion is not None and move.promotion != chess.QUEEN:
        move_type = 64 + (dx + 1) * 3 + _UNDERPROMOTIONS[move.promotion]
    elif (dx, dy) in _KNIGHT_JUMPS:
        move_type = 56 + _KNIGHT_JUMPS[(dx, dy)]
    else:
        distance = max(abs(dx), abs(dy))
        move_type = _QUEEN_DIRECTIONS[(_sign(dx), _sign(dy))] * 7 + distance - 1
    return from_square * MOVE_TYPES + move_type


def legal_actions(board: chess.Board) -> tuple[list[chess.Move], np.ndarray]:
    """Return legal moves and their action indices in the same order."""
    moves = list(board.legal_moves)
    actions = np.fromiter(
        (move_to_action(move, board.turn) for move in moves), dtype=np.int64, count=len(moves)
    )
    return moves, actions
