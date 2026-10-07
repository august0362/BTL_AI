"""Modular evaluation functions for the benchmark alpha-beta bots.

Every evaluator returns a score from the perspective of the side to move, so the
search can use plain negamax. Benchmark 2 reuses ``ai.baseline.evaluate`` through
``material_evaluator``; Benchmark 4 can swap in any function registered here.
"""

from __future__ import annotations

from collections.abc import Callable

import chess

from ai.baseline import PIECE_VALUES, evaluate

MATE_SCORE = 99999

CENTRAL_SQUARES = frozenset({chess.D4, chess.E4, chess.D5, chess.E5})
DEVELOPMENT_SQUARES = frozenset(
    {chess.C3, chess.D3, chess.E3, chess.F3, chess.C6, chess.D6, chess.E6, chess.F6}
)
CENTRAL_BONUS = 20
DEVELOPMENT_BONUS = 8


def material_evaluator(board: chess.Board) -> float:
    """Return the baseline material evaluation from the side to move's view."""
    return _from_white(float(evaluate(board)), board)


def positional_evaluator(board: chess.Board) -> float:
    """Return a modular heuristic: material, central control and development."""
    if board.is_checkmate():
        return _from_white(float(-MATE_SCORE if board.turn == chess.WHITE else MATE_SCORE), board)
    if board.is_stalemate() or board.is_insufficient_material():
        return 0.0
    score = _piece_score(board, chess.WHITE) - _piece_score(board, chess.BLACK)
    return _from_white(score, board)


def register_evaluator(name: str, evaluator: Callable[[chess.Board], float]) -> None:
    """Add or replace a named evaluator used by the custom benchmark bot."""
    EVALUATORS[name] = evaluator


def build_evaluator(name: str = "positional") -> Callable[[chess.Board], float]:
    """Return a named side-to-move evaluator, raising ValueError if unknown."""
    try:
        return EVALUATORS[name]
    except KeyError:
        raise ValueError(f"unknown evaluator: {name!r}") from None


def _piece_score(board: chess.Board, color: chess.Color) -> float:
    score = 0.0
    for square, piece in board.piece_map().items():
        if piece.color != color:
            continue
        score += PIECE_VALUES[piece.piece_type]
        if piece.piece_type in (chess.PAWN, chess.KNIGHT, chess.BISHOP):
            if square in CENTRAL_SQUARES:
                score += CENTRAL_BONUS
            elif square in DEVELOPMENT_SQUARES:
                score += DEVELOPMENT_BONUS
    return score


def _from_white(score: float, board: chess.Board) -> float:
    """Flip a White-perspective score when Black is to move."""
    return score if board.turn == chess.WHITE else -score


EVALUATORS: dict[str, Callable[[chess.Board], float]] = {
    "material": material_evaluator,
    "positional": positional_evaluator,
}
