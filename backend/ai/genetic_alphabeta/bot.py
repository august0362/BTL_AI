"""Alpha-Beta search with genetically evolved evaluation weights (Option 2)."""

from __future__ import annotations

import math
import random
from pathlib import Path

import chess

from ai.base_bot import BaseBot
from ai.genetic_alphabeta.genome import (
    DEFAULT_GENOME,
    WEIGHTS_FILENAME,
    Genome,
    load_genome,
)
from ai.genetic_alphabeta.search import TranspositionTable, search_iterative

MAX_DEPTH = 4
DEFAULT_DEPTH = 3
FAST_DEPTH = 1
EVAL_SCALE = 8.0


def _resolve_settings(config: dict | None) -> dict:
    """Accept a flat per-bot config or the full app config (bots.<id> nested)."""
    config = config or {}
    nested = config.get("bots")
    if isinstance(nested, dict):
        inner = nested.get("genetic_alphabeta")
        if isinstance(inner, dict):
            merged = dict(config)
            merged.update(inner)
            return merged
    return config


def _resolve_depth(settings: dict) -> int:
    """Pick search depth: explicit `depth`, else 1 on fast_mode, else 3."""
    default = FAST_DEPTH if settings.get("fast_mode") else DEFAULT_DEPTH
    try:
        depth = int(settings.get("depth", default))
    except (TypeError, ValueError):
        return default
    return min(max(depth, 1), MAX_DEPTH)


def _resolve_time_limit(settings: dict) -> float | None:
    """Per-move budget in seconds; None (or <= 0) means search to full depth."""
    if "max_think_time_s" not in settings:
        return None
    try:
        seconds = float(settings["max_think_time_s"])
    except (TypeError, ValueError):
        return None
    return None if seconds <= 0 else seconds


def _resolve_genome(settings: dict) -> Genome:
    """Pick evaluation weights: `genome` config wins, then weights.json, else default."""
    override = settings.get("genome")
    try:
        if isinstance(override, Genome):
            return override
        if isinstance(override, list):
            return Genome.from_list([float(v) for v in override])
        if isinstance(override, dict):
            return Genome.from_dict({k: float(v) for k, v in override.items()})
        weights_path = Path(__file__).with_name(WEIGHTS_FILENAME)
        if weights_path.is_file():
            return load_genome(weights_path)
    except (ValueError, OSError, TypeError):
        pass
    return DEFAULT_GENOME


def _normalize(score: float) -> float:
    """Map a pawn-unit score (mover's perspective) into [-1, 1]."""
    return math.tanh(score / EVAL_SCALE)


class GeneticAlphaBetaBot(BaseBot):
    """Play minimax with alpha-beta pruning and GA-evolved weights."""

    bot_id = "genetic_alphabeta"
    display_name = "Genetic Alpha-Beta"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        settings = _resolve_settings(self.config)
        self._rng = random.Random(settings.get("seed"))
        self._depth = _resolve_depth(settings)
        self._time_limit_s = _resolve_time_limit(settings)
        self._genome = _resolve_genome(settings)
        self._tt = TranspositionTable()
        self._killers: dict[int, chess.Move] = {}

    def reset(self) -> None:
        """Drop cached transpositions and killer moves between games."""
        super().reset()
        self._tt.clear()
        self._killers.clear()

    def select_move(self, board: chess.Board) -> chess.Move:
        """Search the position and return a legal move (board left unchanged)."""
        moves = sorted(board.legal_moves, key=lambda move: move.uci())
        if not moves:
            raise ValueError("genetic_alphabeta: no legal moves")
        if len(moves) == 1:
            self.last_search_info = {"depth": 0, "nodes": 1, "eval": 0.0}
            return moves[0]
        move, nodes, score, reached = search_iterative(
            board,
            self._genome,
            self._depth,
            self._rng,
            self._tt,
            self._killers,
            self._time_limit_s,
        )
        self.last_search_info = {
            "depth": reached,
            "nodes": nodes,
            "eval": _normalize(score),
        }
        return move
