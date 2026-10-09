"""Benchmark 7 "Dragon" bot, loaded through ai.registry."""

from __future__ import annotations

import chess

from ai.base_bot import BaseBot
from ai.benchmarks_extension.bench7.evaluation import Evaluator6
from ai.benchmarks_extension.bench7.profile import B7, Profile7
from ai.benchmarks_extension.bench7.search import Engine6

DEFAULT_TIME_LIMIT_S = 1.0
MAX_DEPTH = 64
UNLIMITED_DEPTH = 5  # depth cap when the time budget is switched off


def resolve_time_limit(config: dict) -> float | None:
    """Per-move budget: ``max_think_time_s`` (default 1 s); ``<= 0`` means no limit."""
    if "max_think_time_s" not in config:
        return DEFAULT_TIME_LIMIT_S
    try:
        seconds = float(config["max_think_time_s"])
    except (TypeError, ValueError):
        return DEFAULT_TIME_LIMIT_S
    return None if seconds <= 0 else seconds


def resolve_depth(config: dict, time_limit_s: float | None) -> int:
    """Depth cap: explicit ``depth``, else 2 in fast mode, else time-bound."""
    if "depth" in config:
        try:
            return min(max(int(config["depth"]), 1), MAX_DEPTH)
        except (TypeError, ValueError):
            pass
    if config.get("fast_mode"):
        return 2
    return UNLIMITED_DEPTH if time_limit_s is None else MAX_DEPTH


class Benchmark7Bot(BaseBot):
    """Benchmark 7 "Dragon": the strongest combination of the Benchmark 6 designs."""

    bot_id = "bench7"
    display_name = "Benchmark 7 - Dragon"
    profile: Profile7 = B7

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.time_limit_s = resolve_time_limit(self.config)
        self.max_depth = resolve_depth(self.config, self.time_limit_s)
        seed = self.config.get("seed")
        self._engine = Engine6(
            self.profile.search,
            Evaluator6(self.profile.evaluation),
            seed if isinstance(seed, int) and seed >= 0 else None,
        )

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the best move found within the time budget."""
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError(f"{self.bot_id}: no legal moves")
        if len(moves) == 1:
            self.last_search_info = {"depth": 0, "nodes": 1, "eval": 0.0}
            return moves[0]
        result = self._engine.search(board, self.time_limit_s, self.max_depth)
        self.last_search_info = {
            "depth": result.depth,
            "nodes": result.nodes,
            "eval": float(result.score),
        }
        return result.move

    def reset(self) -> None:
        """Clear the transposition table, histories and caches between games."""
        super().reset()
        self._engine.clear()
