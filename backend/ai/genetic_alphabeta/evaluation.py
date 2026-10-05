"""Static board evaluation used by the Genetic Alpha-Beta bot."""

from __future__ import annotations

import chess

from ai.genetic_alphabeta.genome import Genome

CENTER_SQUARES = frozenset(chess.square(file, rank) for file in range(2, 6) for rank in range(2, 6))


def center_count(board: chess.Board, color: chess.Color) -> int:
    """Count `color` pieces standing on the central 4x4 squares (c3-f6)."""
    return sum(1 for square in CENTER_SQUARES if (p := board.piece_at(square)) and p.color == color)


def mobility_count(board: chess.Board, color: chess.Color) -> int:
    """Count legal moves available to `color` without mutating the board."""
    probe = board.copy(stack=False)
    probe.turn = color
    return sum(1 for _ in probe.legal_moves)


def shield_count(board: chess.Board, color: chess.Color) -> int:
    """Count friendly pawns adjacent to the king (pawn shield)."""
    king = board.king(color)
    if king is None:
        return 0
    shield = chess.SquareSet(chess.BB_KING_ATTACKS[king])
    return sum(
        1
        for square in shield
        if (p := board.piece_at(square)) and p.color == color and p.piece_type == chess.PAWN
    )


def evaluate(board: chess.Board, genome: Genome) -> float:
    """Score the position in pawn units from White's perspective.

    The board is never mutated. Positive favors White, negative favors Black.
    """
    score = 0.0
    for piece in board.piece_map().values():
        value = genome.piece_value(piece.piece_type)
        score += value if piece.color == chess.WHITE else -value
    score += genome.center * (center_count(board, chess.WHITE) - center_count(board, chess.BLACK))
    score += genome.mobility * (
        mobility_count(board, chess.WHITE) - mobility_count(board, chess.BLACK)
    )
    score += genome.shield * (shield_count(board, chess.WHITE) - shield_count(board, chess.BLACK))
    return score
