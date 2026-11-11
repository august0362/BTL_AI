"""Exact chess outcomes and scalar rewards from the side to move's view."""

from __future__ import annotations

import chess


def outcome(board: chess.Board) -> chess.Outcome | None:
    """Return an actual result, including repetition or a 50-move draw now.

    A possible draw after the next move does not count. Retain move history.
    """
    result = board.outcome(claim_draw=False)
    if result is not None:
        return result
    if board.is_repetition(3):
        return chess.Outcome(chess.Termination.THREEFOLD_REPETITION, None)
    if board.halfmove_clock >= 100:
        return chess.Outcome(chess.Termination.FIFTY_MOVES, None)
    return None


def utility(winner: chess.Color | None, player: chess.Color) -> float:
    """Return +1 for a win, 0 for a draw, or -1 for a loss for ``player``."""
    if winner is None:
        return 0.0
    return 1.0 if winner == player else -1.0
