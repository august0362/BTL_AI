"""Đặc tả backend/tournament/series.py — documents/CONTEXT.md §4.6."""

import random

import pytest

from tests._helpers import require_module
from tests.tournament.fakes import FirstLegalPlayer, FoolsMatePlayer

series = require_module("tournament.series")
types_ = require_module("core.types")


def test_series_colors():
    assert series.series_colors(1, random.Random(0)) == [True]
    for seed in range(10):
        colors = series.series_colors(3, random.Random(seed))
        assert colors[:2] == [True, False]
        assert colors[2] in (True, False)
    third = {series.series_colors(3, random.Random(s))[2] for s in range(50)}
    assert third == {True, False}, "ván 3 phải bốc thăm"


@pytest.mark.parametrize("n", [0, 2, 4])
def test_invalid_length(n):
    with pytest.raises(ValueError):
        series.SeriesRunner(FirstLegalPlayer(), FirstLegalPlayer(), n)


def test_best_of_three_colors_and_scores():
    # FoolsMatePlayer: bên đen luôn thắng => kết quả chỉ phụ thuộc màu quân.
    a, b = FoolsMatePlayer("A"), FoolsMatePlayer("B")
    ended = []
    res = series.SeriesRunner(a, b, 3, rng=random.Random(5), on_game_end=ended.append).play()
    assert len(res.games) == 3 and ended == res.games
    g1, g2, g3 = res.games
    assert (g1.white_id, g1.black_id) == ("A", "B")
    assert (g2.white_id, g2.black_id) == ("B", "A")
    assert [g.series_game_index for g in res.games] == [1, 2, 3]
    assert {g.series_id for g in res.games} == {res.series_id}
    assert all(g.mode == "bot_vs_bot" for g in res.games)
    a_white_in_g3 = g3.white_id == "A"
    assert (res.score_a, res.score_b) == ((1.0, 2.0) if a_white_in_g3 else (2.0, 1.0))
    assert res.winner == ("b" if a_white_in_g3 else "a")
    assert (res.a_id, res.b_id) == ("A", "B")
    assert res.aborted is False


def test_draw_series_has_no_winner():
    res = series.SeriesRunner(FirstLegalPlayer("x"), FirstLegalPlayer("y"), 1, max_plies=2).play()
    assert res.games[0].result.winner is None
    assert (res.score_a, res.score_b) == (0.5, 0.5)
    assert res.winner is None


def test_shared_random_opening():
    res = series.SeriesRunner(
        FirstLegalPlayer("x"),
        FirstLegalPlayer("y"),
        3,
        random_opening_plies=2,
        max_plies=6,
        rng=random.Random(9),
    ).play()
    openings = [g.opening_moves for g in res.games]
    assert len(openings[0]) == 2
    assert openings[0] == openings[1] == openings[2]


def test_abort_stops_series():
    holder = {}

    def on_move(rec, state):
        holder["s"].request_stop()

    runner = series.SeriesRunner(FirstLegalPlayer("x"), FirstLegalPlayer("y"), 3, on_move=on_move)
    holder["s"] = runner
    res = runner.play()
    assert res.aborted is True
    assert res.winner is None
    assert len(res.games) == 1
    assert res.games[0].result.termination == types_.Termination.ABORTED
