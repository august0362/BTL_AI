"""Benchmark 5 bots (one class per profile), loaded through ai.registry."""

from __future__ import annotations

import chess

from ai.base_bot import BaseBot
from ai.benchmarks_extension.bench5.evaluation import Evaluator5
from ai.benchmarks_extension.bench5.profiles import PROFILES, Profile5
from ai.benchmarks_extension.bench5.search import Engine5

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


class _Benchmark5Bot(BaseBot):
    """Time-managed PVS bot configured by one Benchmark 5 profile."""

    profile: Profile5

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.time_limit_s = resolve_time_limit(self.config)
        self.max_depth = resolve_depth(self.config, self.time_limit_s)
        self._engine = Engine5(self.profile.search, Evaluator5(self.profile.evaluation))

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
        """Clear the transposition table, history and caches between games."""
        super().reset()
        self._engine.clear()


class Benchmark5GptBot(_Benchmark5Bot):
    """Benchmark 5 built only from the ChatGPT design (``chatgpt.txt``)."""

    bot_id = "bench5_gpt"
    display_name = "Benchmark 5 - GPT"
    profile = PROFILES["gpt"]


class Benchmark5GeminiBot(_Benchmark5Bot):
    """Benchmark 5 built only from the Gemini design (``gemini.txt``)."""

    bot_id = "bench5_gemini"
    display_name = "Benchmark 5 - Gemini"
    profile = PROFILES["gemini"]


class Benchmark5DeepSeekBot(_Benchmark5Bot):
    """Benchmark 5 built only from the DeepSeek design (``deepseek.txt``)."""

    bot_id = "bench5_deepseek"
    display_name = "Benchmark 5 - DeepSeek"
    profile = PROFILES["deepseek"]


class Benchmark5GrokBot(_Benchmark5Bot):
    """Benchmark 5 built only from the Grok design (``grok.txt``)."""

    bot_id = "bench5_grok"
    display_name = "Benchmark 5 - Grok"
    profile = PROFILES["grok"]


class Benchmark5HybridBot(_Benchmark5Bot):
    """Benchmark 5 combining the four designs, tuned by matches."""

    bot_id = "bench5_hybrid"
    display_name = "Benchmark 5 - Hybrid"
    profile = PROFILES["hybrid"]
