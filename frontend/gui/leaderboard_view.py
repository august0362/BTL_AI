"""Pygame-independent leaderboard presentation rows."""

from dataclasses import dataclass

from gui.i18n import Translator
from tournament.ranking import Ranking


@dataclass(frozen=True)
class LeaderboardRow:
    """One localized player row in leaderboard display order."""

    rank: int
    player_id: str
    name: str
    games: int
    wins: int
    draws: int
    losses: int
    points: float
    elo: int


def leaderboard_rows(ranking: Ranking, translator: Translator) -> list[LeaderboardRow]:
    """Build localized display rows in the ranking's authoritative order."""
    rows: list[LeaderboardRow] = []
    for rank, (player_id, stats) in enumerate(ranking.table(), start=1):
        rows.append(
            LeaderboardRow(
                rank=rank,
                player_id=player_id,
                name=translator.t(f"players.{player_id}"),
                games=stats.games,
                wins=stats.wins,
                draws=stats.draws,
                losses=stats.losses,
                points=stats.points,
                elo=round(stats.elo),
            )
        )
    return rows
