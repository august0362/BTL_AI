"""Benchmark 9 "Super Alpha-Beta NNUE" bot, loaded through ai.registry."""

from __future__ import annotations

import logging
import os
import time
import weakref
from collections import deque
from pathlib import Path

import chess
import chess.engine

from ai.base_bot import BaseBot, BotUnavailableError
from ai.benchmarks_extension.bench9.engine import EngineError, EngineSettings, UciEngine
from ai.benchmarks_extension.bench9.provenance import default_engine_path

LOG = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENGINE_PATH_ENV = "BENCH9_ENGINE_PATH"
INSTALL_HINT = "run: python -m ai.benchmarks_extension.bench9.install"

DEFAULT_TIME_LIMIT_S = 1.0
UNLIMITED_DEPTH = 20  # depth cap when the time budget is switched off
FAST_MODE_TIME_S = 0.05
MAX_DEPTH = 245
MATE_SCORE = 100_000
# Time policy: movetime = budget - safety - (largest overhead seen in the last moves).
DEFAULT_TIME_SAFETY_S = 0.03
INITIAL_OVERHEAD_S = 0.03
OVERHEAD_WINDOW = 12
MIN_MOVETIME_S = 0.01


def resolve_time_limit(config: dict) -> float | None:
    """Per-move budget: ``max_think_time_s`` (default 1 s); ``<= 0`` means no limit."""
    if "max_think_time_s" not in config:
        return DEFAULT_TIME_LIMIT_S
    try:
        seconds = float(config["max_think_time_s"])
    except (TypeError, ValueError):
        return DEFAULT_TIME_LIMIT_S
    return None if seconds <= 0 else seconds


def resolve_depth(config: dict, time_limit_s: float | None) -> int | None:
    """Depth cap: explicit ``depth``, else none (time-bound), else 20 without a budget."""
    if "depth" in config:
        try:
            return min(max(int(config["depth"]), 1), MAX_DEPTH)
        except (TypeError, ValueError):
            pass
    return UNLIMITED_DEPTH if time_limit_s is None else None


def _positive_int(config: dict, key: str, default: int) -> int:
    try:
        return max(1, int(config.get(key, default)))
    except (TypeError, ValueError):
        return default


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_engine_path(config: dict) -> Path:
    """Engine binary: ``engine_path``, else $BENCH9_ENGINE_PATH, else the installed build."""
    value = config.get("engine_path") or os.environ.get(ENGINE_PATH_ENV)
    path = _project_path(value) if isinstance(value, str) and value.strip() else None
    if path is None:
        path = default_engine_path()
    if path is None:
        raise BotUnavailableError(
            f"Benchmark 9: no Stockfish build for this platform; {INSTALL_HINT}"
        )
    if not path.is_file():
        raise BotUnavailableError(f"Benchmark 9: engine not found at {path}; {INSTALL_HINT}")
    return path


def resolve_settings(config: dict) -> EngineSettings:
    """Engine launch settings from ``[bots.bench_super_alphabeta_nnue]``."""
    nnue = config.get("nnue_path")
    nnue_path = _project_path(nnue) if isinstance(nnue, str) and nnue.strip() else None
    if nnue_path is not None and not nnue_path.is_file():
        raise BotUnavailableError(f"Benchmark 9: NNUE file not found at {nnue_path}")
    syzygy = config.get("syzygy_path")
    syzygy_path = None
    if isinstance(syzygy, str) and syzygy.strip():
        if Path(syzygy).expanduser().is_dir():
            syzygy_path = str(Path(syzygy).expanduser())
        else:
            LOG.warning("Benchmark 9: syzygy_path %s is not a folder; tablebases off", syzygy)
    return EngineSettings(
        path=resolve_engine_path(config),
        threads=_positive_int(config, "threads", 1),
        hash_mb=_positive_int(config, "hash_mb", 16),
        nnue_path=nnue_path,
        syzygy_path=syzygy_path,
    )


class SuperAlphaBetaNNUEBot(BaseBot):
    """Benchmark 9: Stockfish 19 (alpha-beta + NNUE) over UCI, within the move budget."""

    bot_id = "bench_super_alphabeta_nnue"
    display_name = "B9 · Super Alpha-Beta NNUE"

    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.time_limit_s = resolve_time_limit(self.config)
        self.depth_limit = resolve_depth(self.config, self.time_limit_s)
        self.fast_mode = bool(self.config.get("fast_mode"))
        try:
            self.time_safety_s = max(
                0.0, float(self.config.get("time_safety_s", DEFAULT_TIME_SAFETY_S))
            )
        except (TypeError, ValueError):
            self.time_safety_s = DEFAULT_TIME_SAFETY_S
        self.failures = 0  # searches that needed an engine restart
        self._overheads: deque[float] = deque(maxlen=OVERHEAD_WINDOW)
        self._game = object()
        self._engine = UciEngine(resolve_settings(self.config))
        try:
            self._engine.start()
        except EngineError as exc:
            raise BotUnavailableError(f"Benchmark 9: {exc}") from exc
        self.engine_name = self._engine.name
        self.network = self._engine.network
        self._finalizer = weakref.finalize(self, self._engine.close)

    def _movetime(self) -> float | None:
        """Seconds to give the engine, or None when only the depth cap applies."""
        if self.fast_mode:
            return min(self.time_limit_s or FAST_MODE_TIME_S, FAST_MODE_TIME_S)
        if self.time_limit_s is None:
            return None
        overhead = max(self._overheads, default=INITIAL_OVERHEAD_S)
        return max(MIN_MOVETIME_S, self.time_limit_s - self.time_safety_s - overhead)

    def select_move(self, board: chess.Board) -> chess.Move:
        """Return the engine's best move found within the time budget."""
        started = time.perf_counter()
        if not self._finalizer.alive:
            raise RuntimeError(f"{self.bot_id}: bot was closed")
        moves = list(board.legal_moves)
        if not moves:
            raise ValueError(f"{self.bot_id}: no legal moves")
        if len(moves) == 1:
            self.last_search_info = {"depth": 0, "nodes": 1, "eval": 0.0}
            return moves[0]
        movetime = self._movetime()
        limit = chess.engine.Limit(time=movetime, depth=self.depth_limit)
        try:
            result = self._engine.search(board, limit, self._game)
        except EngineError as exc:
            return self._recover(board, exc, started)
        if movetime is not None and self.depth_limit is None:
            self._overheads.append(max(0.0, time.perf_counter() - started - movetime))
        self.last_search_info = self._search_info(result, board.turn)
        return result.move

    def _recover(self, board: chess.Board, error: EngineError, started: float) -> chess.Move:
        """Restart a failed engine once and re-search with the time left; else raise."""
        self.failures += 1
        LOG.warning("%s: engine failure %d (%s); restarting", self.bot_id, self.failures, error)
        try:
            self._engine.start()
            self.engine_name = self._engine.name
            self._game = object()
            spent = time.perf_counter() - started
            budget = (self.time_limit_s or 1.0) - self.time_safety_s - spent
            limit = chess.engine.Limit(time=max(MIN_MOVETIME_S, budget), depth=self.depth_limit)
            result = self._engine.search(board, limit, self._game)
        except EngineError as exc:
            raise RuntimeError(f"{self.bot_id}: engine failed and did not recover: {exc}") from exc
        info = self._search_info(result, board.turn)
        info.update({"fallback": True, "engine_error": str(error)})
        self.last_search_info = info
        return result.move

    @staticmethod
    def _search_info(result: chess.engine.PlayResult, turn: chess.Color) -> dict:
        """Depth, nodes, speed and score (centipawns for the side to move)."""
        info = result.info
        out: dict = {
            "depth": int(info.get("depth", 0)),
            "seldepth": int(info.get("seldepth", 0)),
            "nodes": int(info.get("nodes", 0)),
            "nps": int(info.get("nps", 0)),
        }
        score = info.get("score")
        if score is not None:
            pov = score.pov(turn)
            out["eval"] = float(pov.score(mate_score=MATE_SCORE))
            if pov.is_mate():
                out["mate"] = pov.mate()
        return out

    def reset(self) -> None:
        """Start a new game: the next search sends ``ucinewgame`` (clears the hash)."""
        super().reset()
        self._game = object()

    def external_memory_bytes(self) -> int:
        """Peak memory of the engine process, which the tournament worker cannot see."""
        return self._engine.peak_memory_bytes()

    def close(self) -> None:
        """Stop the engine process (also done automatically when the bot is collected)."""
        self._finalizer()
