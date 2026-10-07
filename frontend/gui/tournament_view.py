"""Pygame-independent presentation helpers for the AI ranking screens."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from tournament.round_robin import Matchup, StandingRow


@dataclass(frozen=True)
class TournamentRow:
    """One localized row of the AI ranking table."""

    rank: int
    player_id: str
    name: str
    games: int
    wins: int
    draws: int
    losses: int
    points: float
    think_time_s: float


def tournament_rows(standings: Sequence[StandingRow], translator) -> list[TournamentRow]:
    """Project standings into localized rows, keeping their order and rank."""
    return [
        TournamentRow(
            rank=row.rank,
            player_id=row.bot_id,
            name=translator.t(f"players.{row.bot_id}"),
            games=row.games,
            wins=row.wins,
            draws=row.draws,
            losses=row.losses,
            points=row.points,
            think_time_s=row.think_time_s,
        )
        for row in standings
    ]


def provisional_standings(bot_ids: Sequence[str]) -> tuple[StandingRow, ...]:
    """Return a zeroed table that seeds every bot in its configured order.

    Used before any tournament has been played so the ranking screen already
    lists all participants (ranks 1..n) instead of an empty table.
    """
    return tuple(
        StandingRow(
            bot_id=bot_id,
            rank=index + 1,
            points=0.0,
            games=0,
            wins=0,
            draws=0,
            losses=0,
            think_time_s=0.0,
            score_pct=0.0,
        )
        for index, bot_id in enumerate(bot_ids)
    )


def format_points(points: float) -> str:
    """Format match points without a trailing ``.0``."""
    return f"{points:g}"


def format_seconds(seconds: float) -> str:
    """Format a thinking-time total in seconds."""
    return f"{seconds:.1f}s"


def format_head_to_head(matchup: Matchup) -> str:
    """Format a head-to-head score such as ``15 - 5``."""
    return f"{matchup.score_a:g} - {matchup.score_b:g}"


def format_matchup(matchup: Matchup, translator) -> str:
    """Format a localized head-to-head line with both bot names."""
    name_a = translator.t(f"players.{matchup.bot_a}")
    name_b = translator.t(f"players.{matchup.bot_b}")
    return f"{name_a}  {format_head_to_head(matchup)}  {name_b}"


def progress_fraction(done: int, total: int) -> float:
    """Return a safe 0..1 progress fraction."""
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, done / total))
