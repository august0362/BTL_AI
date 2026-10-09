"""Estimated remaining time of a tournament, from exponentially smoothed game durations.

Each bot keeps its own smoothed thinking time per game, ``E = a * x + (1 - a) * E``, and one
more smoothed value covers the per-game overhead (process start, opening, bookkeeping). The
remaining time is the sum of those estimates over the games still in the schedule, so slow
and fast bots weigh correctly whatever order the challenges come in.
"""

from __future__ import annotations

from collections.abc import Iterable

DEFAULT_SMOOTHING = 0.3


class GameTimeEstimator:
    """Smoothed per-bot thinking time per game plus a smoothed per-game overhead."""

    def __init__(self, smoothing: float = DEFAULT_SMOOTHING) -> None:
        if not 0.0 < smoothing <= 1.0:
            raise ValueError("smoothing must be in (0, 1]")
        self.smoothing = smoothing
        self._think: dict[str, float] = {}
        self._overhead: float | None = None

    def _smooth(self, old: float | None, value: float) -> float:
        return value if old is None else self.smoothing * value + (1.0 - self.smoothing) * old

    def update(
        self, white_id: str, white_s: float, black_id: str, black_s: float, wall_s: float
    ) -> None:
        """Record one finished game: each side's thinking time and the game's wall time."""
        self._think[white_id] = self._smooth(self._think.get(white_id), white_s)
        self._think[black_id] = self._smooth(self._think.get(black_id), black_s)
        self._overhead = self._smooth(self._overhead, max(0.0, wall_s - white_s - black_s))

    def game_seconds(self, white_id: str, black_id: str) -> float | None:
        """Expected duration of one game; bots not seen yet use the average bot. None = no data."""
        if not self._think:
            return None
        default = sum(self._think.values()) / len(self._think)
        return (
            self._think.get(white_id, default)
            + self._think.get(black_id, default)
            + (self._overhead or 0.0)
        )

    def remaining_seconds(
        self, games: Iterable[tuple[str, str]], current_elapsed_s: float = 0.0
    ) -> float | None:
        """Expected time left for ``games`` (White, Black); the first one is already running
        for ``current_elapsed_s`` seconds. None until a game has been measured."""
        total = 0.0
        for index, (white_id, black_id) in enumerate(games):
            seconds = self.game_seconds(white_id, black_id)
            if seconds is None:
                return None
            total += max(0.0, seconds - current_elapsed_s) if index == 0 else seconds
        return total
