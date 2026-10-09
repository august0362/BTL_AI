"""Đặc tả lớp trình bày bảng xếp hạng AI (không cần pygame)."""

from gui.i18n import Translator
from gui.tournament_view import (
    format_head_to_head,
    format_matchup,
    format_points,
    format_seconds,
    progress_fraction,
    provisional_standings,
    tournament_rows,
)
from tournament.round_robin import Matchup, StandingRow


def make_row(bot_id: str, rank: int, points: float, **overrides) -> StandingRow:
    values = {
        "games": 20,
        "wins": 10,
        "draws": 4,
        "losses": 6,
        "think_time_s": 12.34,
        "score_pct": points / 20,
    }
    values.update(overrides)
    return StandingRow(bot_id=bot_id, rank=rank, points=points, **values)


def test_rows_follow_standings_order_and_localize_names():
    translator = Translator("en")
    standings = (make_row("mcts", 1, 15.0), make_row("deep_rl", 2, 5.0))

    rows = tournament_rows(standings, translator)

    assert [row.player_id for row in rows] == ["mcts", "deep_rl"]
    assert [row.rank for row in rows] == [1, 2]
    assert rows[0].name == translator.t("players.mcts")
    assert rows[0].points == 15.0
    assert rows[0].think_time_s == 12.34


def test_format_points_and_seconds():
    assert format_points(0.0) == "0"
    assert format_points(2.0) == "2"
    assert format_points(2.5) == "2.5"
    assert format_points(15.0) == "15"
    assert format_seconds(12.34) == "12.3s"
    assert format_seconds(0.0) == "0.0s"


def test_head_to_head_and_matchup_formatting():
    translator = Translator("en")
    matchup = Matchup("mcts", "deep_rl", games=20, wins_a=15, wins_b=5, score_a=15.0, score_b=5.0)
    assert format_head_to_head(matchup) == "15 - 5"
    assert format_matchup(matchup, translator) == (
        f"{translator.t('players.mcts')}  15 - 5  {translator.t('players.deep_rl')}"
    )
    drawn = Matchup("mcts", "deep_rl", games=1, score_a=0.5, score_b=0.5)
    assert format_head_to_head(drawn) == "0.5 - 0.5"


def test_progress_fraction_is_clamped():
    assert progress_fraction(0, 0) == 0.0
    assert progress_fraction(5, 10) == 0.5
    assert progress_fraction(10, 10) == 1.0
    assert progress_fraction(20, 10) == 1.0
    assert progress_fraction(-3, 10) == 0.0


def test_provisional_standings_seed_every_bot_in_order():
    rows = provisional_standings(["bench_random", "mcts", "deep_rl"])
    assert [row.bot_id for row in rows] == ["bench_random", "mcts", "deep_rl"]
    assert [row.rank for row in rows] == [1, 2, 3]
    assert all(row.points == 0.0 and row.games == 0 and row.score_pct == 0.0 for row in rows)


def test_sort_rows_by_column_keeps_rank_numbers():
    from gui.tournament_view import TournamentRow, sort_rows

    rows = [
        TournamentRow(1, "a", "A", 4, 3, 0, 1, 3.0, 10.0, 3.1),
        TournamentRow(2, "b", "B", 4, 1, 3, 0, 2.5, 30.0, 2.4),
        TournamentRow(3, "c", "C", 4, 0, 1, 3, 0.5, 20.0, 0.5),
    ]
    assert [row.player_id for row in sort_rows(rows, "total")] == ["a", "b", "c"]
    assert [row.player_id for row in sort_rows(rows, "draws")] == ["b", "c", "a"]
    assert [row.player_id for row in sort_rows(rows, "think_time_s")] == ["b", "c", "a"]
    assert [row.rank for row in sort_rows(rows, "losses")] == [3, 1, 2]


def test_format_duration():
    from gui.tournament_view import format_duration

    assert format_duration(0) == "0:00"
    assert format_duration(65.4) == "1:05"
    assert format_duration(3_725) == "1:02:05"
