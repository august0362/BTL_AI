"""Threaded bridge between GUI screens and the tournament runners."""

from __future__ import annotations

import random
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import chess

from core.types import MoveRecord
from tournament.history import History
from tournament.match_runner import MatchRunner
from tournament.players import HumanPlayer, Player
from tournament.ranking import Ranking
from tournament.records import GameRecord
from tournament.series import SeriesResult, SeriesRunner


@dataclass(frozen=True)
class ControllerSnapshot:
    """Immutable view of the controller's current game and series."""

    board: chess.Board
    moves: tuple[MoveRecord, ...]
    game_index: int
    n_games: int
    finished_games: tuple[GameRecord, ...]
    series_result: SeriesResult | None
    thinking: bool
    waiting_for_human: bool
    finished: bool
    paused: bool


class _TrackedPlayer:
    """Track when a player is selecting a move while forwarding its interface."""

    def __init__(self, player: Player, controller: GameController) -> None:
        self._player = player
        self._controller = controller
        self.bot_id = player.bot_id
        self.display_name = player.display_name

    @property
    def last_search_info(self) -> dict:
        return getattr(self._player, "last_search_info", {})

    def select_move(self, board: chess.Board) -> chess.Move:
        is_human = isinstance(self._player, HumanPlayer)
        with self._controller._lock:
            if is_human:
                self._controller._waiting_for_human = True
            else:
                self._controller._thinking = True
        try:
            return self._player.select_move(board)
        finally:
            with self._controller._lock:
                if is_human:
                    self._controller._waiting_for_human = False
                else:
                    self._controller._thinking = False

    def reset(self) -> None:
        self._player.reset()

    def cancel(self) -> None:
        cancel = getattr(self._player, "cancel", None)
        if cancel is not None:
            cancel()

    def submit_move(self, move: chess.Move) -> None:
        submit = getattr(self._player, "submit_move", None)
        if submit is None:
            raise RuntimeError("Player is not a HumanPlayer")
        submit(move)


class GameController:
    """Run tournament games in a background thread and expose safe snapshots."""

    def __init__(
        self,
        white: Player,
        black: Player,
        *,
        mode: str,
        config: dict,
        n_games: int = 1,
        ranking: Ranking | None = None,
        history: History | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if mode not in ("human_vs_bot", "bot_vs_bot"):
            raise ValueError("mode must be 'human_vs_bot' or 'bot_vs_bot'")
        if mode == "human_vs_bot" and n_games != 1:
            raise ValueError("human_vs_bot supports exactly one game")
        if mode == "bot_vs_bot" and n_games not in (1, 3):
            raise ValueError("n_games must be 1 or 3")

        game_config = config.get("game", {})
        eval_config = config.get("eval_bar", {})
        ui_config = config.get("ui", {})
        self._mode = mode
        self._n_games = n_games
        self._max_plies = game_config.get("max_plies", 300)
        self._claim_draw = game_config.get("claim_draw", True)
        self._random_opening_plies = (
            game_config.get("random_opening_plies", 2) if mode == "bot_vs_bot" else 0
        )
        self._eval_scale = eval_config.get("scale", 8.0)
        self._delay_s = ui_config.get("bot_move_delay_ms", 300) / 1000
        self._ranking = ranking
        self._history = history
        self._rng = rng if rng is not None else random.Random()
        self._human_player = next(
            (player for player in (white, black) if isinstance(player, HumanPlayer)), None
        )
        self._white = _TrackedPlayer(white, self)
        self._black = _TrackedPlayer(black, self)

        self._lock = threading.Lock()
        self._delay_condition = threading.Condition()
        self._board = chess.Board()
        self._moves: list[MoveRecord] = []
        self._game_index = 1
        self._finished_games: list[GameRecord] = []
        self._series_result: SeriesResult | None = None
        self._thinking = False
        self._waiting_for_human = False
        self._finished = False
        self._paused = False
        self._started = False
        self._stop_event = threading.Event()
        self._runner: MatchRunner | SeriesRunner | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background game exactly once."""
        with self._lock:
            if self._started:
                raise RuntimeError("controller already started")
            self._started = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            thread = self._thread
        thread.start()

    def snapshot(self) -> ControllerSnapshot:
        """Return a consistent snapshot with an independent board copy."""
        with self._lock:
            return ControllerSnapshot(
                board=self._board.copy(),
                moves=deepcopy(tuple(self._moves)),
                game_index=self._game_index,
                n_games=self._n_games,
                finished_games=deepcopy(tuple(self._finished_games)),
                series_result=deepcopy(self._series_result),
                thinking=self._thinking,
                waiting_for_human=self._waiting_for_human,
                finished=self._finished,
                paused=self._paused,
            )

    def submit_human_move(self, move: chess.Move) -> None:
        """Submit a move to the human player if one is waiting."""
        with self._lock:
            human = self._human_player
            waiting = self._waiting_for_human
        if human is None or not waiting:
            return
        human.submit_move(move)

    def human_color(self) -> chess.Color | None:
        """Return the human's assigned color, or None for bot versus bot."""
        if self._human_player is None:
            return None
        return chess.WHITE if self._human_player is self._white._player else chess.BLACK

    def stop(self) -> None:
        """Request an immediate stop, including during an inter-move delay."""
        self._stop_event.set()
        with self._delay_condition:
            self._delay_condition.notify_all()
        with self._lock:
            runner = self._runner
        if runner is not None:
            runner.request_stop()

    def pause(self) -> None:
        """Pause before the next move, including when called before start."""
        with self._lock:
            self._paused = True
            runner = self._runner
        if runner is not None:
            runner.pause()

    def resume(self) -> None:
        """Resume a paused game or series."""
        with self._lock:
            self._paused = False
            runner = self._runner
        if runner is not None:
            runner.resume()

    def set_bot_move_delay(self, ms: int) -> None:
        """Change the Bot vs Bot delay and wake an active delay wait."""
        with self._delay_condition:
            self._delay_s = max(0, int(ms)) / 1000
            self._delay_condition.notify_all()

    def join(self, timeout: float | None = None) -> bool:
        """Wait up to timeout for the worker thread to finish."""
        with self._lock:
            thread = self._thread
        if thread is None:
            return self._finished
        thread.join(timeout)
        return not thread.is_alive()

    def _run(self) -> None:
        try:
            if self._mode == "human_vs_bot":
                self._run_human_match()
            else:
                self._run_series()
        except Exception:
            # A worker failure must never escape into the GUI thread.
            pass
        finally:
            with self._lock:
                self._thinking = False
                self._waiting_for_human = False
                self._finished = True

    def _make_runner_options(self, on_move: Any) -> dict:
        return {
            "max_plies": self._max_plies,
            "claim_draw": self._claim_draw,
            "eval_scale": self._eval_scale,
            "rng": self._rng,
            "on_move": on_move,
        }

    def _set_runner(self, runner: MatchRunner | SeriesRunner) -> None:
        with self._lock:
            self._runner = runner
            paused = self._paused
            stopped = self._stop_event.is_set()
        if paused:
            runner.pause()
        if stopped:
            runner.request_stop()

    def _run_human_match(self) -> None:
        runner = MatchRunner(
            self._white,
            self._black,
            mode=self._mode,
            random_opening_plies=0,
            **self._make_runner_options(self._on_move),
        )
        self._set_runner(runner)
        record = runner.play()
        self._record_game(record)

    def _run_series(self) -> None:
        runner = SeriesRunner(
            self._white,
            self._black,
            self._n_games,
            random_opening_plies=self._random_opening_plies,
            on_game_end=self._record_game,
            **self._make_runner_options(self._on_move),
        )
        self._set_runner(runner)
        result = runner.play()
        with self._lock:
            self._series_result = result

    def _on_move(self, move: MoveRecord, state: Any) -> None:
        with self._lock:
            self._board = state.board
            self._moves.append(move)
        if self._mode == "bot_vs_bot" and not move.is_random_opening:
            started = time.monotonic()
            with self._delay_condition:
                while not self._stop_event.is_set():
                    remaining = self._delay_s - (time.monotonic() - started)
                    if remaining <= 0:
                        break
                    self._delay_condition.wait(remaining)

    def _record_game(self, record: GameRecord) -> None:
        if self._history is not None:
            self._history.save(record)
        if self._ranking is not None:
            self._ranking.record_game(record)
        with self._lock:
            self._finished_games.append(record)
            if len(self._finished_games) < self._n_games:
                self._game_index = len(self._finished_games) + 1
                self._board = chess.Board()
                self._moves = []
