"""Shared random implementation for bots that are not implemented yet."""

import random

import chess

from ai.base_bot import BaseBot


class RandomBaselineBot(BaseBot):
    """Choose uniformly from legal moves using a per-instance random generator."""

    is_baseline = True

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._rng = random.Random(self.config.get("seed"))

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a uniformly selected legal move, ordered for seed stability."""
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        move = self._rng.choice(moves)
        self.last_search_info = {}
        return move
