"""Threaded bridge between the GUI and the round-robin tournament runner."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from itertools import combinations

from core.config import get_bot_config
from tournament.round_robin import RoundRobinRunner, StandingRow, TournamentResult
from tournament.tournament_config import TournamentConfig
from tournament.tournament_history import TournamentHistory


@dataclass(frozen=True)
class TournamentSnapshot:
    """Immutable view of the tournament controller's current state."""

    running: bool
    finished: bool
    stopped: bool
    games_done: int
    games_total: int
    current_pair: tuple[str, str] | None
    standings: tuple[StandingRow, ...]
    result: TournamentResult | None
    error: str | None
    plies_current: int = 0
    plies_limit: int = 0
    elapsed_s: float = 0.0  # time since the tournament started
    eta_s: float | None = None  # estimated time left (None while not yet known)

    @property
    def progress(self) -> float:
        """Return overall progress in the 0..1 range, counting the current game."""
        if self.games_total <= 0:
            return 0.0
        within_game = 0.0
        if self.plies_limit > 0:
            within_game = min(1.0, max(0.0, self.plies_current / self.plies_limit))
        return max(0.0, min(1.0, (self.games_done + within_game) / self.games_total))


class TournamentController:
    """Run an AI ranking tournament in a background thread."""

    def __init__(
        self,
        config: dict,
        *,
        settings: TournamentConfig | None = None,
        history: TournamentHistory | None = None,
        create_bot=None,
    ) -> None:
        self.settings = settings or TournamentConfig.from_config(config)
        self._bot_configs = {
            bot_id: get_bot_config(config, bot_id) for bot_id in self.settings.bots
        }
        self._history = history
        self._create_bot = create_bot
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._runner: RoundRobinRunner | None = None
        self._result: TournamentResult | None = None
        self._running = False
        self._finished = False
        self._stopped = False
        self._error: str | None = None
        self._games_done = 0
        self._plies_current = 0
        self._games_total = (
            2 * len(tuple(combinations(self.settings.bots, 2))) * self.settings.matches_per_pair
        )
        self._current_pair: tuple[str, str] | None = None

    def start(self) -> None:
        """Start the tournament in a background thread exactly once per run."""
        with self._lock:
            if self._running:
                raise RuntimeError("tournament already running")
            self._running = True
            self._finished = False
            self._stopped = False
            self._error = None
            self._result = None
            self._games_done = 0
            self._plies_current = 0
            self._current_pair = None
            self._stop_requested = False
            self._thread = threading.Thread(target=self._run, name="tournament", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Ask the running tournament to stop after the current game."""
        with self._lock:
            self._stop_requested = True
            runner = self._runner
        if runner is not None:
            runner.request_stop()

    def join(self, timeout: float | None = None) -> bool:
        """Wait up to timeout for the worker thread to finish."""
        with self._lock:
            thread = self._thread
        if thread is None:
            return self._finished
        thread.join(timeout)
        return not thread.is_alive()

    def snapshot(self) -> TournamentSnapshot:
        """Return a thread-safe snapshot of the current state."""
        with self._lock:
            runner = self._runner
            result = self._result
            running = self._running
            finished = self._finished
            stopped = self._stopped
            error = self._error
            games_done = self._games_done
            games_total = self._games_total
            plies_current = self._plies_current
            current_pair = self._current_pair
        elapsed_s, eta_s = 0.0, None
        if running and runner is not None:
            elapsed_s, eta_s = runner.time_status()
            standings = runner.standings()
            # The game being played now, challenger (White) first.
            current_pair = runner.current_game
        elif result is not None:
            standings = result.standings
        else:
            standings = ()
        return TournamentSnapshot(
            running=running,
            finished=finished,
            stopped=stopped,
            games_done=games_done,
            games_total=games_total,
            current_pair=current_pair,
            standings=standings,
            result=result,
            error=error,
            plies_current=plies_current,
            plies_limit=self.settings.max_plies,
            elapsed_s=elapsed_s,
            eta_s=eta_s,
        )

    def _on_progress(self, done: int, total: int, pair: tuple[str, str] | None) -> None:
        with self._lock:
            self._games_done = done
            self._games_total = total
            self._plies_current = 0
            if self._running:
                self._current_pair = pair

    def _on_ply(self, ply: int) -> None:
        with self._lock:
            self._plies_current = ply

    def _run(self) -> None:
        runner = RoundRobinRunner(
            self.settings.bots,
            matches_per_pair=self.settings.matches_per_pair,
            max_plies=self.settings.max_plies,
            claim_draw=self.settings.claim_draw,
            random_opening_plies=self.settings.random_opening_plies,
            depth=self.settings.depth,
            max_think_time_s=self.settings.max_think_time_s,
            bot_configs=self._bot_configs,
            seed=None if self.settings.seed < 0 else self.settings.seed,
            on_progress=self._on_progress,
            on_ply=self._on_ply,
            create_bot=self._create_bot,
            measure_memory=self.settings.measure_memory,
            eta_smoothing=self.settings.eta_smoothing,
        )
        with self._lock:
            self._runner = runner
            stop_requested = self._stop_requested
        if stop_requested:
            runner.request_stop()
        result: TournamentResult | None = None
        try:
            result = runner.play()
            if result.completed and self._history is not None:
                try:
                    result = self._history.save(result)
                except OSError as exc:  # pragma: no cover - disk failures are rare
                    with self._lock:
                        self._error = str(exc)
        except Exception as exc:  # noqa: BLE001 - a worker failure must not reach the GUI
            with self._lock:
                self._error = str(exc)
        finally:
            with self._lock:
                self._runner = None
                self._running = False
                self._finished = True
                self._result = result
                self._stopped = result is not None and not result.completed
                if result is not None:
                    self._games_done = result.games_played
                    self._games_total = result.games_total
                    self._plies_current = 0
                self._current_pair = None
