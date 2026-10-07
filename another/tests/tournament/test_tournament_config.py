"""Đặc tả bảng [tournament] — documents/CONTEXT.md §4.9, §6."""

import pytest

from tournament.tournament_config import TournamentConfig


def test_defaults_when_the_table_is_missing():
    settings = TournamentConfig.from_config({})
    assert len(settings.bots) == 8
    assert "bench_random" in settings.bots
    assert settings.matches_per_pair == 20
    assert settings.max_history == 10
    assert settings.max_plies == 150
    assert settings.depth == 0  # 0 = không ép độ sâu
    assert settings.max_think_time_s == 1.0
    assert settings.claim_draw is True
    assert settings.random_opening_plies == 2
    settings.validate()


def test_values_are_read_from_the_table():
    settings = TournamentConfig.from_config(
        {
            "tournament": {
                "bots": ["bench_random", "bench_alphabeta3"],
                "matches_per_pair": 4,
                "max_history": 3,
                "max_plies": 60,
                "depth": 5,
                "random_opening_plies": 0,
                "claim_draw": False,
                "seed": 7,
                "max_think_time_s": 0.4,
            }
        }
    )
    assert settings.bots == ("bench_random", "bench_alphabeta3")
    assert settings.matches_per_pair == 4
    assert settings.max_history == 3
    assert settings.max_plies == 60
    assert settings.depth == 5
    assert settings.random_opening_plies == 0
    assert settings.claim_draw is False
    assert settings.seed == 7
    assert settings.max_think_time_s == 0.4


def test_bad_values_fall_back_instead_of_crashing():
    settings = TournamentConfig.from_config(
        {
            "tournament": {
                "bots": ["only_one"],
                "matches_per_pair": "nhieu",
                "max_plies": -3,
                "depth": -1,
                "max_think_time_s": "nhanh",
            }
        }
    )
    assert len(settings.bots) == 8
    assert settings.matches_per_pair == 20
    assert settings.max_plies == 1
    assert settings.depth == 0
    assert settings.max_think_time_s == 1.0


def test_duplicate_bots_fall_back_to_the_default_list():
    settings = TournamentConfig.from_config({"tournament": {"bots": ["mcts", "mcts", "deep_rl"]}})
    assert len(settings.bots) == 8
    assert len(set(settings.bots)) == 8


def test_negative_time_limit_means_no_limit():
    settings = TournamentConfig.from_config({"tournament": {"max_think_time_s": -1}})
    assert settings.max_think_time_s == 0.0


@pytest.mark.parametrize(
    "settings",
    [
        TournamentConfig(bots=("a",)),
        TournamentConfig(bots=("a", "a")),
        TournamentConfig(bots=("a", "b"), matches_per_pair=0),
        TournamentConfig(bots=("a", "b"), max_plies=0),
        TournamentConfig(bots=("a", "b"), depth=-1),
        TournamentConfig(bots=("a", "b"), max_think_time_s=-0.5),
        TournamentConfig(bots=("a", "b"), max_history=0),
        TournamentConfig(bots=("a", "b"), random_opening_plies=-1),
    ],
)
def test_validate_rejects_bad_settings(settings):
    with pytest.raises(ValueError):
        settings.validate()


def test_validate_accepts_zero_depth_and_zero_time_limit():
    TournamentConfig(bots=("a", "b"), depth=0, max_think_time_s=0.0).validate()
