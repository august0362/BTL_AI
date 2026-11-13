"""Short adversarial leaf checks; chess rules and legal moves come from python-chess."""

from __future__ import annotations

import time
from collections.abc import Callable

import chess

from ai.mcts.evaluation import _MIDDLE, PIECE_VALUES, positional_score

MATE = 100_000


class LeafTimeout(Exception):
    """Stop a leaf probe and unwind every pushed move."""


class LeafEvaluator:
    """Check replies and exchanges before feeding a heuristic reward into MCTS."""

    def __init__(
        self,
        depth: int,
        *,
        deadline: float | None = None,
        clock: Callable[[], float] = time.perf_counter,
        claim_draw: bool = True,
    ) -> None:
        self.depth, self.deadline, self.clock = depth, deadline, clock
        self.claim_draw = claim_draw
        self.nodes = 0

    def evaluate(self, board: chess.Board) -> float:
        """Return centipawns for White, keeping the input board and history intact."""
        if self.deadline is not None and self.clock() >= self.deadline:
            raise LeafTimeout
        value = self._search(board, self.depth, 4, -MATE, MATE, 0)
        return value if board.turn else -value

    @staticmethod
    def _priority(board: chess.Board, move: chess.Move) -> int:
        victim = board.piece_type_at(move.to_square)
        if board.is_en_passant(move):
            victim = chess.PAWN
        attacker = board.piece_type_at(move.from_square) or chess.PAWN
        capture = 10_000 + 10 * PIECE_VALUES[victim] - PIECE_VALUES[attacker] if victim else 0
        promotion = 10 * PIECE_VALUES[move.promotion] if move.promotion else 0
        origin = move.from_square if board.turn else move.from_square ^ 56
        target = move.to_square if board.turn else move.to_square ^ 56
        return capture + promotion + _MIDDLE[attacker][target] - _MIDDLE[attacker][origin]

    def _search(
        self, board: chess.Board, depth: int, exchanges: int, alpha: float, beta: float, ply: int
    ) -> float:
        self.nodes += 1
        if self.nodes % 32 == 0 and self.deadline is not None and self.clock() >= self.deadline:
            raise LeafTimeout
        in_check = board.is_check()
        moves = list(board.legal_moves) if depth > 0 or in_check else None
        if moves == [] or (moves is None and not any(board.generate_legal_moves())):
            return -MATE + ply if in_check else 0.0
        if (
            board.is_insufficient_material()
            or board.halfmove_clock >= (100 if self.claim_draw else 150)
            or (board.halfmove_clock >= 8 and board.is_repetition(3 if self.claim_draw else 5))
        ):
            return 0.0
        static = positional_score(board) * (1 if board.turn else -1)
        if depth <= 0 and exchanges <= 0:
            return static
        if depth > 0 or in_check:
            best = -float("inf")
        else:
            best = static
            if best >= beta:
                return best
            alpha = max(alpha, best)
            moves = list(board.generate_legal_captures())
            pawns = board.pawns & board.occupied_co[board.turn]
            promoting = pawns & (chess.BB_RANK_7 if board.turn else chess.BB_RANK_2)
            if promoting:
                moves += [
                    m
                    for m in board.generate_legal_moves(from_mask=promoting)
                    if m.promotion and not board.is_capture(m)
                ]
        assert moves is not None
        for move in sorted(moves, key=lambda m: self._priority(board, m), reverse=True):
            board.push(move)
            try:
                value = -self._search(
                    board, depth - 1, exchanges - int(depth <= 0), -beta, -alpha, ply + 1
                )
            finally:
                board.pop()
            best, alpha = max(best, value), max(alpha, value)
            if alpha >= beta:
                break
        return best
