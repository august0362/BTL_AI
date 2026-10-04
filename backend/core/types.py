"""Shared value types for chess games."""

from dataclasses import dataclass
from enum import StrEnum

import chess


class Termination(StrEnum):
    """Stable reasons a game can end."""

    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    THREEFOLD_REPETITION = "threefold_repetition"
    FIFTY_MOVES = "fifty_moves"
    MAX_PLIES = "max_plies"
    ABORTED = "aborted"


class IllegalMoveError(ValueError):
    """Raised when a move is not legal in the current position."""


class GameOverError(RuntimeError):
    """Raised when attempting to play after a game has ended."""


@dataclass(frozen=True)
class GameResult:
    """The winner and termination reason for a completed game."""

    winner: chess.Color | None
    termination: Termination

    def score_for(self, color: chess.Color) -> float:
        """Return this result's score from the given color's perspective."""
        if self.termination is Termination.ABORTED:
            raise ValueError("An aborted game has no score")
        if self.winner is None:
            return 0.5
        return 1.0 if self.winner == color else 0.0


@dataclass(frozen=True)
class MoveRecord:
    """Recorded details about one played move."""

    ply: int
    uci: str
    san: str
    think_time_s: float
    search_info: dict
    material_eval: float
    is_random_opening: bool
