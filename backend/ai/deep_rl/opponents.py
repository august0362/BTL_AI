"""Opponent policies used by training and evaluation tools."""

from __future__ import annotations

import math
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


_MATE_SCORE = 10_000


class MaterialAlphaBetaOpponent:
    """Like Benchmark 1.5: negamax alpha-beta at fixed depth, score = own minus enemy material.

    Written here because ``deep_rl`` may not import the benchmark package. Captures are searched
    first (same result, faster); ties at the root are broken with ``rng`` so games vary.
    """

    def __init__(self, depth: int = 3) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        self.depth = depth

    def select_move(self, board: chess.Board, rng: random.Random | None = None) -> chess.Move:
        """Return a best move of the fixed-depth search."""
        source = rng or random
        alpha, best_moves = -math.inf, []
        for move in self._ordered(board):
            board.push(move)
            score = -self._negamax(board, self.depth - 1, -math.inf, -alpha + 1e-9, 1)
            board.pop()
            if score > alpha:
                alpha, best_moves = score, [move]
            elif score == alpha:
                best_moves.append(move)
        return source.choice(best_moves)

    def _negamax(
        self, board: chess.Board, depth: int, alpha: float, beta: float, ply: int
    ) -> float:
        if board.is_checkmate():
            return -(_MATE_SCORE - ply)
        if board.is_stalemate() or board.is_insufficient_material():
            return 0.0
        if depth == 0:
            return float(_material(board, board.turn) - _material(board, not board.turn))
        best = -math.inf
        for move in self._ordered(board):
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    @staticmethod
    def _ordered(board: chess.Board) -> list[chess.Move]:
        moves = list(board.legal_moves)
        moves.sort(key=lambda move: not board.is_capture(move))
        return moves


def _material(board: chess.Board, color: chess.Color) -> int:
    return sum(
        value * len(board.pieces(piece_type, color)) for piece_type, value in _VALUES.items()
    )


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
