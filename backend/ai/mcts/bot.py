"""Time-bounded UCT bot with optional, explicitly labelled heuristic assistance."""

from __future__ import annotations

import math
import random
import time

import chess

from ai.base_bot import BaseBot
from ai.mcts.search import SearchConfig, search


class MctsBot(BaseBot):
    """Search a fresh MCTS tree for each move; never retain a caller's board."""

    bot_id = "mcts"
    display_name = "MCTS"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._rng = random.Random(self.config.get("seed"))
        fast = bool(self.config.get("fast_mode", False))
        seconds = self._number("max_think_time_s", 0.05 if fast else 1.0)
        exploration = self._number("exploration_constant", math.sqrt(2.0))
        if seconds < 0 or exploration < 0:
            raise ValueError("mcts: time and exploration_constant must be non-negative")
        heuristics = self.config.get("use_heuristics", True)
        if not isinstance(heuristics, bool):
            raise ValueError("mcts: use_heuristics must be a boolean")
        simulations = self._integer("simulations", 32 if fast else 100_000, minimum=1)
        plies = self._integer("rollout_max_plies", 4 if heuristics else 120, minimum=0)
        self.search_config = SearchConfig(
            simulations=min(simulations, 32) if fast else simulations,
            exploration_constant=exploration,
            rollout_max_plies=min(plies, 4) if fast else plies,
            max_think_time_s=min(seconds, 0.05) if fast and seconds > 0 else seconds,
            use_heuristics=heuristics,
            claim_draw=bool(self.config.get("claim_draw", True)),
        )

    def _number(self, key: str, default: float) -> float:
        value = self.config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"mcts: {key} must be a finite number")
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"mcts: {key} must be a finite number")
        return result

    def _integer(self, key: str, default: int, *, minimum: int) -> int:
        value = self.config.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"mcts: {key} must be an integer >= {minimum}")
        return value

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the most visited root move within the configured search budget."""
        self.last_search_info = {}
        started = time.perf_counter()
        result = search(board, self.search_config, self._rng, started=started)
        self.last_search_info = result.info
        return result.move
