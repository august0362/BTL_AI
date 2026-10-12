from __future__ import annotations

import numpy as np
import pytest

from ai.deep_rl.user.train import _draw_mate_level, _MateProgress, _parse_mate_review

REVIEW = "2:1=0.25;3:1=0.10,2=0.15;4:1=0.05,2=0.08,3=0.12"


def test_parse_mate_review_example() -> None:
    assert _parse_mate_review(REVIEW) == {
        2: {1: 0.25},
        3: {1: 0.10, 2: 0.15},
        4: {1: 0.05, 2: 0.08, 3: 0.12},
    }


@pytest.mark.parametrize(
    "value",
    ["2:2=0.2", "3:1=0.7,2=0.4", "5:1=0.2", "2:1=-0.1", "oops"],
)
def test_parse_mate_review_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="invalid mate_review"):
        _parse_mate_review(value)


def test_mate_review_level_draw_shares() -> None:
    probabilities = _parse_mate_review(REVIEW)
    rng = np.random.default_rng(174)
    draws = [_draw_mate_level(4, probabilities, rng) for _ in range(20_000)]

    for level, expected in ((1, 0.05), (2, 0.08), (3, 0.12), (4, 0.75)):
        assert sum(draw == level for draw in draws) / len(draws) == pytest.approx(
            expected, abs=0.01
        )
    assert {_draw_mate_level(1, probabilities, rng) for _ in range(100)} == {1}


def test_review_results_do_not_change_current_level_gating() -> None:
    progress = _MateProgress(max_level=2, window=3, pass_rate=0.8, min_games=4, max_games=2)
    assert progress.record(False, 1) is None
    assert progress.record(False, 1) == (1, 2, 0.0)
    progress.record(True, 1)  # review game while level 2 is current

    assert progress.level == 2
    assert progress.games_by_level[1] == 3
    assert progress.games_by_level[2] == 0
    assert progress.games == 0
    assert np.isnan(progress.rate)
    progress.record(False, 2)
    assert progress.games == 1
    assert progress.rate == 0.0
