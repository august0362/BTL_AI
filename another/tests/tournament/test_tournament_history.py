"""Đặc tả lịch sử "Trận Chiến Lần n" của giải xếp hạng AI."""

from tournament.round_robin import Matchup, StandingRow, TournamentResult
from tournament.tournament_history import TournamentHistory


def make_result(name: str = "run") -> TournamentResult:
    rows = (
        StandingRow(
            bot_id="alpha",
            rank=1,
            points=2.0,
            games=2,
            wins=2,
            draws=0,
            losses=0,
            think_time_s=1.5,
            score_pct=1.0,
        ),
        StandingRow(
            bot_id="beta",
            rank=2,
            points=0.0,
            games=2,
            wins=0,
            draws=0,
            losses=2,
            think_time_s=2.5,
            score_pct=0.0,
        ),
    )
    return TournamentResult(
        tournament_id=name,
        created_at="2026-10-07T00:00:00.000000+00:00",
        participants=("alpha", "beta"),
        matches_per_pair=2,
        completed=True,
        games_played=2,
        games_total=2,
        standings=rows,
        matchups=(Matchup("alpha", "beta", 2, 2, 0, 0, 2.0, 0.0),),
    )


def test_directory_created(tmp_path):
    directory = tmp_path / "tournaments"
    TournamentHistory(directory)
    assert directory.is_dir()


def test_battle_numbers_auto_increment(tmp_path):
    history = TournamentHistory(tmp_path)
    assert history.next_index() == 1
    for expected in (1, 2, 3):
        saved = history.save(make_result(f"run{expected}"))
        assert saved.battle == expected
    assert history.next_index() == 4
    assert [item.battle for item in history.list()] == [3, 2, 1]


def test_prune_keeps_only_the_newest_runs(tmp_path):
    history = TournamentHistory(tmp_path, max_runs=3)
    for _ in range(5):
        history.save(make_result())
    assert [item.battle for item in history.list()] == [5, 4, 3]
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        "battle_0003.json",
        "battle_0004.json",
        "battle_0005.json",
    ]


def test_next_index_continues_after_pruning(tmp_path):
    history = TournamentHistory(tmp_path, max_runs=10)
    for _ in range(12):
        history.save(make_result())
    assert history.next_index() == 13
    assert len(history.list()) == 10


def test_load_roundtrip(tmp_path):
    history = TournamentHistory(tmp_path)
    saved = history.save(make_result())
    loaded = history.load(saved.battle)
    assert loaded.standings == saved.standings
    assert loaded.matchups == saved.matchups
    assert loaded.completed is True


def test_corrupt_files_are_skipped(tmp_path):
    history = TournamentHistory(tmp_path)
    history.save(make_result())
    (tmp_path / "battle_9999.json").write_text("{oops", encoding="utf-8")
    assert len(history.list()) == 1


def test_clear_removes_every_battle(tmp_path):
    history = TournamentHistory(tmp_path)
    history.save(make_result())
    history.clear()
    assert history.list() == []
    assert history.next_index() == 1
