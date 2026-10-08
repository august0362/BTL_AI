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
    total: float = 0.0
    memory_mb: float = 0.0


def tournament_rows(standings: Sequence[StandingRow], translator) -> list[TournamentRow]:
    """Project standings into localized rows numbered 1..n in table order (ties stay ordered)."""
    return [
        TournamentRow(
            rank=index + 1,
            player_id=row.bot_id,
            name=translator.t(f"players.{row.bot_id}"),
            games=row.games,
            wins=row.wins,
            draws=row.draws,
            losses=row.losses,
            points=row.points,
            think_time_s=row.think_time_s,
            total=row.total,
            memory_mb=row.memory_mb,
        )
        for index, row in enumerate(standings)
    ]


SORT_FIELDS = (
    "games",
    "wins",
    "draws",
    "losses",
    "points",
    "think_time_s",
    "memory_mb",
    "total",
)
DEFAULT_SORT = "total"


def sort_rows(rows: Sequence[TournamentRow], field: str) -> list[TournamentRow]:
    """Order rows by one column, highest first; ``total`` keeps the ranking order.

    Ties keep the ranking order, so the rank column stays meaningful while sorted.
    """
    if field == DEFAULT_SORT or field not in SORT_FIELDS:
        return list(rows)
    return sorted(rows, key=lambda row: (-getattr(row, field), row.rank))


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


def format_total(total: float) -> str:
    """Format the time-adjusted total with two decimals."""
    return f"{total:.2f}"


def format_seconds(seconds: float) -> str:
    """Format a thinking-time total in seconds."""
    return f"{seconds:.1f}s"


def format_memory(megabytes: float) -> str:
    """Format the average peak memory per game; ``-`` when it was not measured."""
    return f"{megabytes:.1f} MB" if megabytes > 0 else "-"


def format_duration(seconds: float) -> str:
    """Format a duration as ``h:mm:ss`` (or ``m:ss`` under an hour)."""
    total = max(0, round(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


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
