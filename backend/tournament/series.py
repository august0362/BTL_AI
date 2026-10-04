"""Run one game or a best-of-three series."""

from __future__ import annotations

import random
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import chess

from core.types import Termination
from tournament.match_runner import MatchRunner, generate_random_opening
from tournament.players import Player
from tournament.records import GameRecord


def series_colors(n_games: int, rng: random.Random) -> list[bool]:
    """Return whether player A has White in each game."""
    if n_games == 1:
        return [True]
    if n_games == 3:
        return [True, False, rng.choice([True, False])]
    raise ValueError("n_games must be 1 or 3")


@dataclass
class SeriesResult:
    """Results and score totals for a series."""

    series_id: str
    a_id: str
    b_id: str
    games: list[GameRecord] = field(default_factory=list)
    score_a: float = 0.0
    score_b: float = 0.0
    winner: str | None = None
    aborted: bool = False


class SeriesRunner:
    """Coordinate a single game or best-of-three between two players."""

    def __init__(
        self,
        player_a: Player,
        player_b: Player,
        n_games: int,
        *,
        random_opening_plies: int = 0,
        max_plies: int = 300,
        claim_draw: bool = True,
        eval_scale: float = 8.0,
        rng: random.Random | None = None,
        on_move=None,
        on_game_end: Callable[[GameRecord], None] | None = None,
    ) -> None:
        if n_games not in (1, 3):
            raise ValueError("n_games must be 1 or 3")
        self.player_a = player_a
        self.player_b = player_b
        self.n_games = n_games
        self.random_opening_plies = random_opening_plies
        self.max_plies = max_plies
        self.claim_draw = claim_draw
        self.eval_scale = eval_scale
        self.rng = rng if rng is not None else random.Random()
        self.on_move = on_move
        self.on_game_end = on_game_end
        self.series_id = uuid.uuid4().hex
        self._current_runner: MatchRunner | None = None
        self._runner_lock = threading.Lock()
        self._stop_requested = False
        self._paused = False

    def request_stop(self) -> None:
        """Request that the current game and series stop."""
        with self._runner_lock:
            self._stop_requested = True
            runner = self._current_runner
        if runner is not None:
            runner.request_stop()

    def pause(self) -> None:
        """Pause the current game before its next move."""
        with self._runner_lock:
            self._paused = True
            runner = self._current_runner
        if runner is not None:
            runner.pause()

    def resume(self) -> None:
        """Resume the current game."""
        with self._runner_lock:
            self._paused = False
            runner = self._current_runner
        if runner is not None:
            runner.resume()

    def play(self) -> SeriesResult:
        """Play every scheduled game unless a game is aborted."""
        colors = series_colors(self.n_games, self.rng)
        opening = (
            generate_random_opening(self.random_opening_plies, self.rng)
            if self.random_opening_plies > 0
            else []
        )
        result = SeriesResult(self.series_id, self.player_a.bot_id, self.player_b.bot_id)

        for index, a_is_white in enumerate(colors, start=1):
            if self._stop_requested:
                result.aborted = True
                break
            white, black = (
                (self.player_a, self.player_b) if a_is_white else (self.player_b, self.player_a)
            )
            runner = MatchRunner(
                white,
                black,
                mode="bot_vs_bot",
                opening_moves=opening,
                max_plies=self.max_plies,
                claim_draw=self.claim_draw,
                eval_scale=self.eval_scale,
                rng=self.rng,
                on_move=self.on_move,
                series_id=self.series_id,
                series_game_index=index,
            )
            with self._runner_lock:
                self._current_runner = runner
                if self._paused:
                    runner.pause()
                if self._stop_requested:
                    runner.request_stop()
            game = runner.play()
            with self._runner_lock:
                self._current_runner = None
            result.games.append(game)
            if self.on_game_end is not None:
                self.on_game_end(game)
            if game.result.termination is Termination.ABORTED:
                result.aborted = True
                result.winner = None
                break
            if game.result.winner is None:
                result.score_a += 0.5
                result.score_b += 0.5
            elif game.result.winner == chess.WHITE:
                if a_is_white:
                    result.score_a += 1.0
                else:
                    result.score_b += 1.0
            elif a_is_white:
                result.score_b += 1.0
            else:
                result.score_a += 1.0

        if not result.aborted:
            if result.score_a > result.score_b:
                result.winner = "a"
            elif result.score_b > result.score_a:
                result.winner = "b"
        return result
