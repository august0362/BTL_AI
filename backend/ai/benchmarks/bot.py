"""Benchmark bots forming the strength ladder used by the AI ranking tournament."""

from __future__ import annotations

import random

import chess

from ai.base_bot import BaseBot
from ai.benchmarks.evaluation import build_evaluator
from ai.benchmarks.search import SearchResult, TranspositionTable, alpha_beta_iterative

DEFAULT_DEPTH = 3
FAST_DEPTH = 1
MAX_DEPTH = 6
DEFAULT_TIME_LIMIT_S: float | None = None


def resolve_depth(config: dict) -> int:
    """Resolve a search depth: explicit ``depth``, else 1 in fast mode, else 3."""
    default = FAST_DEPTH if config.get("fast_mode") else DEFAULT_DEPTH
    try:
        depth = int(config.get("depth", default))
    except (TypeError, ValueError):
        return default
    return min(max(depth, 1), MAX_DEPTH)


def resolve_time_limit(config: dict) -> float | None:
    """Resolve the per-move time budget in seconds; ``None`` or <= 0 means no limit."""
    if "max_think_time_s" not in config:
        return DEFAULT_TIME_LIMIT_S
    try:
        seconds = float(config["max_think_time_s"])
    except (TypeError, ValueError):
        return DEFAULT_TIME_LIMIT_S
    return None if seconds <= 0 else seconds


class BenchmarkRandomBot(BaseBot):
    """Benchmark 1: pick uniformly from the legal moves with a seeded generator."""

    bot_id = "bench_random"
    display_name = "Benchmark 1 - Random"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._rng = random.Random(self.config.get("seed"))

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return a uniformly selected legal move."""
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        if not moves:
            raise ValueError("bench_random: no legal moves")
        self.last_search_info = {"depth": 0, "nodes": len(moves), "eval": 0.0}
        return self._rng.choice(moves)


class _SearchBenchmarkBot(BaseBot):
    """Common plumbing for the deterministic alpha-beta benchmark bots."""

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.depth = resolve_depth(self.config)
        self.time_limit_s = resolve_time_limit(self.config)

    def _search(self, board: chess.Board) -> SearchResult:
        raise NotImplementedError

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the best move found at the configured depth."""
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError(f"{self.bot_id}: no legal moves")
        if len(moves) == 1:
            self.last_search_info = {"depth": 0, "nodes": 1, "eval": 0.0}
            return moves[0]
        result = self._search(board)
        if result.move is None:
            raise ValueError(f"{self.bot_id}: search returned no move")
        self.last_search_info = {
            "depth": result.depth or self.depth,
            "nodes": result.nodes,
            "eval": result.score,
        }
        return result.move


class BenchmarkMaterialBot(_SearchBenchmarkBot):
    """Benchmark 1.5: plain alpha-beta, score = own material minus the opponent's."""

    bot_id = "bench_alphabeta_material"
    display_name = "Benchmark 1.5 - Alpha-Beta Material"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self._evaluator = build_evaluator("material")

    def _search(self, board: chess.Board) -> SearchResult:
        return alpha_beta_iterative(
            board, self.depth, self._evaluator, time_limit_s=self.time_limit_s
        )


class BenchmarkAlphaBetaBot(_SearchBenchmarkBot):
    """Benchmark 2: fixed-depth alpha-beta with material plus piece-square tables."""

    bot_id = "bench_alphabeta3"
    display_name = "Benchmark 2 - Alpha-Beta 3"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.evaluator_name = str(self.config.get("evaluator", "pst"))
        self._evaluator = build_evaluator(self.evaluator_name)
        self._rng = random.Random(self.config.get("seed"))

    def _search(self, board: chess.Board) -> SearchResult:
        return alpha_beta_iterative(
            board, self.depth, self._evaluator, time_limit_s=self.time_limit_s, rng=self._rng
        )


class BenchmarkAlphaBetaTTBot(_SearchBenchmarkBot):
    """Benchmark 3: Benchmark 2 eval plus a transposition table, ordering and quiescence."""

    bot_id = "bench_alphabeta_tt"
    display_name = "Benchmark 3 - Alpha-Beta TT"
    default_evaluator = "pst"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.evaluator_name = str(self.config.get("evaluator", self.default_evaluator))
        self._evaluator = build_evaluator(self.evaluator_name)
        self._tt = TranspositionTable()
        self._killers: dict[int, chess.Move] = {}

    def _search(self, board: chess.Board) -> SearchResult:
        return alpha_beta_iterative(
            board,
            self.depth,
            self._evaluator,
            tt=self._tt,
            killers=self._killers,
            time_limit_s=self.time_limit_s,
            quiescence=True,
        )

    def reset(self) -> None:
        """Drop cached transpositions and killer moves between games."""
        super().reset()
        self._tt.clear()
        self._killers.clear()


class BenchmarkAlphaBetaCustomBot(BenchmarkAlphaBetaTTBot):
    """Benchmark 4: Benchmark 3 + ``advanced`` eval, check extensions, null-move and LMR."""

    bot_id = "bench_alphabeta_custom"
    display_name = "Benchmark 4 - Alpha-Beta Custom"
    default_evaluator = "advanced"

    def _search(self, board: chess.Board) -> SearchResult:
        return alpha_beta_iterative(
            board,
            self.depth,
            self._evaluator,
            tt=self._tt,
            killers=self._killers,
            time_limit_s=self.time_limit_s,
            quiescence=True,
            pruning=True,
            extend_checks=True,
        )
