"""Đặc tả giải vòng tròn cho bảng xếp hạng AI."""

import chess

from tests.tournament.fakes import FirstLegalPlayer, FoolsMatePlayer
from tournament.round_robin import Matchup, RoundRobinRunner, TournamentResult, compute_standings


class ColorRecorder(FirstLegalPlayer):
    """Ghi lại màu quân của mỗi instance bot (một instance cho mỗi ván)."""

    def __init__(self, bot_id: str, sink: dict[str, int]) -> None:
        super().__init__(bot_id=bot_id)
        self._sink = sink
        self._recorded = False

    def select_move(self, board):
        if not self._recorded:
            self._recorded = True
            color = "white" if board.turn == chess.WHITE else "black"
            key = f"{self.bot_id}_{color}"
            self._sink[key] = self._sink.get(key, 0) + 1
        return super().select_move(board)


def loser_as_white_factory(calls: list[str]):
    def create(bot_id, config):
        calls.append(bot_id)
        return FoolsMatePlayer(bot_id)

    return create


def test_schedule_covers_every_unordered_pair():
    runner = RoundRobinRunner(["a", "b", "c", "d"], matches_per_pair=4, create_bot=lambda *a: None)
    pairs = (("a", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("b", "d"), ("c", "d"))
    assert runner.pairs == pairs
    assert runner.games_total == 6 * 4


def test_colors_are_split_evenly_per_pair():
    sink: dict[str, int] = {}
    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=20,
        max_plies=8,
        random_opening_plies=0,
        create_bot=lambda bot_id, config: ColorRecorder(bot_id, sink),
    )
    runner.play()
    assert sink == {"a_white": 10, "a_black": 10, "b_white": 10, "b_black": 10}


def test_odd_match_count_differs_by_at_most_one_game():
    sink: dict[str, int] = {}
    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=5,
        max_plies=8,
        random_opening_plies=0,
        create_bot=lambda bot_id, config: ColorRecorder(bot_id, sink),
    )
    runner.play()
    assert sink["a_white"] + sink["a_black"] == 5
    assert abs(sink["a_white"] - sink["a_black"]) <= 1
    assert abs(sink["b_white"] - sink["b_black"]) <= 1


def test_a_fresh_bot_instance_is_created_for_every_game():
    calls: list[str] = []
    runner = RoundRobinRunner(
        ["alpha", "beta"],
        matches_per_pair=4,
        max_plies=20,
        random_opening_plies=0,
        create_bot=loser_as_white_factory(calls),
    )
    result = runner.play()
    assert result.games_played == 4
    assert len(calls) == 8


def test_scoring_from_deterministic_games():
    runner = RoundRobinRunner(
        ["alpha", "beta"],
        matches_per_pair=4,
        max_plies=20,
        random_opening_plies=0,
        create_bot=loser_as_white_factory([]),
    )
    result = runner.play()
    assert result.completed is True
    assert result.games_played == result.games_total == 4
    scores = {row.bot_id: row.points for row in result.standings}
    # FoolsMatePlayer loses as White, so each side wins the two games where it has Black.
    assert scores == {"alpha": 2.0, "beta": 2.0}
    matchup = next(item for item in result.matchups if item.bot_a == "alpha")
    assert (matchup.games, matchup.wins_a, matchup.wins_b) == (4, 2, 2)
    assert matchup.score_a == 2.0
    assert {row.rank for row in result.standings} <= {1, 2}
    assert all(row.think_time_s >= 0 for row in result.standings)


def test_standings_share_rank_on_tied_points_and_time():
    matchups = [
        Matchup("a", "b", games=4, wins_a=1, wins_b=1, draws=2, score_a=2.0, score_b=2.0),
        Matchup("c", "d", games=1, wins_a=1, wins_b=0, draws=0, score_a=1.0, score_b=0.0),
    ]
    times = {"a": 1.0, "b": 1.0, "c": 0.5, "d": 0.0}
    standings = compute_standings(["a", "b", "c", "d"], matchups, times)
    assert {row.bot_id: row.rank for row in standings} == {"a": 1, "b": 1, "c": 3, "d": 4}


def test_less_thinking_time_breaks_a_points_tie():
    matchups = [Matchup("a", "b", games=2, wins_a=1, wins_b=1, score_a=1.0, score_b=1.0)]
    standings = compute_standings(["a", "b"], matchups, {"a": 5.0, "b": 1.0})
    assert [row.bot_id for row in standings] == ["b", "a"]
    assert [row.rank for row in standings] == [1, 2]


def test_empty_standings_use_zero_games():
    standings = compute_standings(["a", "b"], [], {})
    assert [row.points for row in standings] == [0.0, 0.0]
    assert all(row.games == 0 and row.score_pct == 0.0 for row in standings)


def test_stop_before_start_returns_incomplete_result():
    runner = RoundRobinRunner(["a", "b"], matches_per_pair=4, create_bot=lambda *a: None)
    runner.request_stop()
    result = runner.play()
    assert result.completed is False
    assert result.games_played == 0


def test_stop_during_a_game_aborts_and_does_not_score():
    runner: RoundRobinRunner | None = None

    class StoppingPlayer(FoolsMatePlayer):
        def select_move(self, board):
            assert runner is not None
            runner.request_stop()
            return super().select_move(board)

    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=4,
        max_plies=20,
        random_opening_plies=0,
        create_bot=lambda bot_id, config: StoppingPlayer(bot_id),
    )
    result = runner.play()
    assert result.completed is False
    assert result.games_played == 1
    assert result.standings[0].points == 0.0


def test_broken_bot_does_not_crash_the_tournament():
    def create(bot_id, config):
        if bot_id == "broken":
            raise RuntimeError("boom")
        return FirstLegalPlayer(bot_id=bot_id)

    runner = RoundRobinRunner(
        ["broken", "ok"], matches_per_pair=2, max_plies=8, random_opening_plies=0, create_bot=create
    )
    result = runner.play()
    assert result.completed is True
    assert result.games_played == 2
    assert result.errors
    assert all(row.points == 0.0 for row in result.standings)


def test_result_json_roundtrip():
    runner = RoundRobinRunner(
        ["alpha", "beta"],
        matches_per_pair=2,
        max_plies=20,
        random_opening_plies=0,
        create_bot=loser_as_white_factory([]),
    )
    result = runner.play()
    restored = TournamentResult.from_json(result.to_json())
    assert restored.participants == result.participants
    assert restored.games_played == result.games_played
    assert restored.standings == result.standings
    assert restored.matchups == result.matchups
    assert restored.battle is None


def test_runner_injects_depth_and_time_budget_into_bot_configs():
    seen: list[dict] = []

    def create(bot_id, config):
        seen.append(dict(config))
        return FirstLegalPlayer(bot_id=bot_id)

    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=2,
        max_plies=8,
        random_opening_plies=0,
        depth=4,
        max_think_time_s=0.25,
        create_bot=create,
    )
    runner.play()
    assert len(seen) == 4
    assert all(config["depth"] == 4 for config in seen)
    assert all(config["max_think_time_s"] == 0.25 for config in seen)


def test_runner_leaves_bot_configs_alone_without_limits():
    seen: list[dict] = []

    def create(bot_id, config):
        seen.append(dict(config))
        return FirstLegalPlayer(bot_id=bot_id)

    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=1,
        max_plies=8,
        random_opening_plies=0,
        create_bot=create,
    )
    runner.play()
    assert all("depth" not in config for config in seen)
    assert all("max_think_time_s" not in config for config in seen)


def test_on_ply_reports_the_half_move_count_of_the_current_game():
    plies: list[int] = []
    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=1,
        max_plies=8,
        random_opening_plies=0,
        create_bot=lambda bot_id, config: FirstLegalPlayer(bot_id=bot_id),
        on_ply=plies.append,
    )
    runner.play()
    assert len(plies) > 1
    assert plies == list(range(1, len(plies) + 1))


def test_zero_depth_does_not_override_participants():
    seen: list[dict] = []

    def create(bot_id, config):
        seen.append(dict(config))
        return FirstLegalPlayer(bot_id=bot_id)

    runner = RoundRobinRunner(
        ["a", "b"],
        matches_per_pair=1,
        max_plies=8,
        random_opening_plies=0,
        depth=0,
        create_bot=create,
    )
    runner.play()
    assert seen
    assert all("depth" not in config for config in seen)
