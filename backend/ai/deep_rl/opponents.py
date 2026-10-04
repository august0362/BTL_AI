"""Opponent policies used by training and evaluation tools."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Protocol

import chess

_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


class Opponent(Protocol):
    """Interface shared by environment opponents."""

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move: ...


class RandomOpponent:
    """Choose uniformly from legal moves."""

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move:
        """Return a uniformly random legal move."""
        return (rng or random).choice(list(board.legal_moves))


class GreedyCaptureOpponent:
    """Prefer the highest-value capture, otherwise play randomly."""

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move:
        """Return a legal capture of maximal victim value when available."""
        source = rng or random
        captures = [move for move in board.legal_moves if board.is_capture(move)]
        if not captures:
            return source.choice(list(board.legal_moves))

        def value(move: chess.Move) -> int:
            victim = board.piece_at(move.to_square)
            if board.is_en_passant(move):
                return _VALUES[chess.PAWN]
            return _VALUES.get(victim.piece_type, 0) if victim else 0

        best = max(value(move) for move in captures)
        return source.choice([move for move in captures if value(move) == best])


@dataclass
class PolicyOpponent:
    """Use an existing policy object as an opponent."""

    policy: object

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move:
        """Ask the wrapped policy to select a move."""
        del rng
        return self.policy.select_move(board.copy())


class MixedOpponent:
    """Sample an opponent from weighted alternatives."""

    def __init__(self, opponents: list[tuple[Opponent, float]]) -> None:
        if not opponents or any(weight <= 0 for _, weight in opponents):
            raise ValueError("opponents and positive weights are required")
        self.opponents = opponents

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move:
        """Choose an opponent by weight and delegate its move selection."""
        source = rng or random
        opponent = source.choices(
            [item for item, _ in self.opponents],
            weights=[weight for _, weight in self.opponents],
            k=1,
        )[0]
        return opponent.select_move(board, source)
