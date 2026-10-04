"""Tests for leaderboard row projection."""

from gui.i18n import Translator
from gui.leaderboard_view import leaderboard_rows
from tournament.ranking import PlayerStats, Ranking


def test_rows_follow_ranking_table_order_and_localize_names() -> None:
    ranking = Ranking(None, known_ids=["human", "mcts", "random"])
    ranking._players = {
        "human": PlayerStats(wins=2, draws=1, losses=1, elo=1500.6),
        "mcts": PlayerStats(wins=3, draws=0, losses=0, elo=1500.4),
    }
    translator = Translator("en")
    expected_order = [player_id for player_id, _ in ranking.table()]

    rows = leaderboard_rows(ranking, translator)

    assert [row.player_id for row in rows] == expected_order
    assert [row.rank for row in rows] == list(range(1, len(rows) + 1))
    human = next(row for row in rows if row.player_id == "human")
    assert human.name == translator.t("players.human")
    assert (human.games, human.wins, human.draws, human.losses) == (4, 2, 1, 1)
    assert human.points == 2.5
    assert human.elo == 1501
