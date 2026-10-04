"""Debug bot that selects uniformly from legal moves."""

import random

import chess

from ai.base_bot import BaseBot
from ai.baseline import RandomBaselineBot


class BaselineBot(RandomBaselineBot):
    """Provide a stable random opponent as a benchmark for tournament bots."""

    bot_id = "baseline"
    display_name = "Baseline"


class RandomBot(BaseBot):
    """Choose a random legal move using a per-instance random generator."""

    bot_id = "random"
    display_name = "Random"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._rng = random.Random(self.config.get("seed"))

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a uniformly selected legal move."""
        return self._rng.choice(list(board.legal_moves))
