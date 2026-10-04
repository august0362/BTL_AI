"""Persistent player statistics and Elo rankings."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import chess

from core.types import Termination
from tournament.records import GameRecord


@dataclass
class PlayerStats:
    """Wins, draws, losses, and Elo for one player."""

    wins: int = 0
    draws: int = 0
    losses: int = 0
    elo: float = 1200.0

    @property
    def games(self) -> int:
        """Return the number of recorded games."""
        return self.wins + self.draws + self.losses

    @property
    def points(self) -> float:
        """Return match points, counting a draw as half a point."""
        return self.wins + 0.5 * self.draws


def expected_score(r_a: float, r_b: float) -> float:
    """Return player A's expected score against player B."""
    return 1 / (1 + 10 ** ((r_b - r_a) / 400))


class Ranking:
    """Maintain player records in memory and optionally persist them as JSON."""

    def __init__(
        self,
        path: Path | None,
        *,
        elo_initial: float = 1200,
        elo_k: float = 32,
        known_ids: Iterable[str] = (),
        debug_ids: Iterable[str] = ("random",),
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.elo_initial = float(elo_initial)
        self.elo_k = float(elo_k)
        self.known_ids = set(known_ids)
        self.debug_ids = set(debug_ids)
        self._players: dict[str, PlayerStats] = {}
        if self.path is not None:
            self._load()

    def stats(self, player_id: str) -> PlayerStats:
        """Return a player's stats, or fresh defaults for an unknown id."""
        stats = self._players.get(player_id)
        if stats is None:
            return PlayerStats(elo=self.elo_initial)
        return stats

    def table(self) -> list[tuple[str, PlayerStats]]:
        """Return known and recorded players ordered by rating and points."""
        player_ids = self.known_ids | self._players.keys()
        return sorted(
            ((player_id, self.stats(player_id)) for player_id in player_ids),
            key=lambda item: (-item[1].elo, -item[1].points, item[0]),
        )

    def record_game(self, record: GameRecord) -> bool:
        """Record a finished game and update both Elo ratings from prior ratings."""
        if (
            record.result.termination is Termination.ABORTED
            or record.white_id == record.black_id
            or record.white_id in self.debug_ids
            or record.black_id in self.debug_ids
        ):
            return False

        white = self._players.setdefault(record.white_id, PlayerStats(elo=self.elo_initial))
        black = self._players.setdefault(record.black_id, PlayerStats(elo=self.elo_initial))
        white_rating, black_rating = white.elo, black.elo
        white_score = record.result.score_for(chess.WHITE)
        black_score = 1.0 - white_score
        white_expected = expected_score(white_rating, black_rating)
        black_expected = 1.0 - white_expected

        if white_score == 1.0:
            white.wins += 1
            black.losses += 1
        elif white_score == 0.0:
            white.losses += 1
            black.wins += 1
        else:
            white.draws += 1
            black.draws += 1
        white.elo = white_rating + self.elo_k * (white_score - white_expected)
        black.elo = black_rating + self.elo_k * (black_score - black_expected)
        self._save()
        return True

    def reset(self) -> None:
        """Clear recorded stats and persist the empty ranking."""
        self._players.clear()
        self._save()

    def _load(self) -> None:
        assert self.path is not None
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data["version"] != 1 or not isinstance(data["players"], dict):
                raise ValueError("Unsupported ranking data")
            players = {
                player_id: PlayerStats(
                    wins=stats["wins"],
                    draws=stats["draws"],
                    losses=stats["losses"],
                    elo=stats["elo"],
                )
                for player_id, stats in data["players"].items()
            }
        except (OSError, ValueError, TypeError, KeyError) as _exc:
            corrupt_path = self.path.with_name(f"{self.path.name}.corrupt")
            try:
                os.replace(self.path, corrupt_path)
            except OSError:
                pass
            return
        self._players = players

    def _save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "players": {
                player_id: {
                    "wins": stats.wins,
                    "draws": stats.draws,
                    "losses": stats.losses,
                    "elo": stats.elo,
                }
                for player_id, stats in self._players.items()
            },
        }
        fd, temporary_name = tempfile.mkstemp(dir=self.path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.path)
        finally:
            temporary_path.unlink(missing_ok=True)
