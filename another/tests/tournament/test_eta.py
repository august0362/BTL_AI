"""Đặc tả ước tính thời gian còn lại của giải — documents/CONTEXT.md §4.9.4."""

import pytest

from tests.tournament.fakes import FirstLegalPlayer
from tournament.eta import GameTimeEstimator
from tournament.round_robin import RoundRobinRunner


def test_smoothing_follows_the_formula():
    estimator = GameTimeEstimator(0.3)
    estimator.update("a", 10.0, "b", 2.0, 13.0)  # first game: values taken as they are
    assert estimator.game_seconds("a", "b") == pytest.approx(10.0 + 2.0 + 1.0)
    estimator.update("a", 20.0, "b", 2.0, 23.0)
    # E_a = 0.3 * 20 + 0.7 * 10 = 13; overhead stays 1.
    assert estimator.game_seconds("a", "b") == pytest.approx(13.0 + 2.0 + 1.0)


def test_unknown_bots_use_the_average_and_no_data_means_none():
    estimator = GameTimeEstimator()
    assert estimator.game_seconds("a", "b") is None
    assert estimator.remaining_seconds([("a", "b")]) is None
    estimator.update("a", 4.0, "b", 2.0, 6.0)
    assert estimator.game_seconds("a", "new") == pytest.approx(4.0 + 3.0)


def test_remaining_time_sums_the_schedule_and_counts_the_running_game():
    estimator = GameTimeEstimator()
    estimator.update("a", 4.0, "b", 6.0, 10.0)
    games = [("a", "b"), ("b", "a"), ("a", "b")]
    assert estimator.remaining_seconds(games) == pytest.approx(30.0)
    assert estimator.remaining_seconds(games, current_elapsed_s=4.0) == pytest.approx(26.0)
    assert estimator.remaining_seconds(games, current_elapsed_s=99.0) == pytest.approx(20.0)


def test_invalid_smoothing_is_rejected():
    with pytest.raises(ValueError):
        GameTimeEstimator(0.0)


def test_runner_reports_elapsed_and_estimate():
    clock = [0.0]

    def tick() -> float:
        clock[0] += 0.5
        return clock[0]

    statuses = []
    holder: list[RoundRobinRunner] = []
    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=2,
        max_plies=4,
        random_opening_plies=0,
        create_bot=lambda bot_id, config: FirstLegalPlayer(bot_id=bot_id),
        clock=tick,
        on_progress=lambda done, total, pair: statuses.append(holder[0].time_status()),
    )
    holder.append(runner)
    assert runner.time_status() == (0.0, None)
    runner.play()
    elapsed, eta = statuses[0]
    assert elapsed > 0 and eta is not None and eta > 0
    assert statuses[-1][1] == 0.0
