"""Đặc tả backend/tournament/ranking.py — documents/CONTEXT.md §4.7."""

import json

import chess
import pytest

from tests._helpers import require_module

ranking = require_module("tournament.ranking")
records = require_module("tournament.records")
types_ = require_module("core.types")
T = types_.Termination

BOTS = ["alphabeta_regression", "genetic_alphabeta", "mcts", "deep_rl", "human"]


def rec(white, black, winner, termination=T.CHECKMATE):
    return records.GameRecord(
        game_id=f"{white}-{black}",
        started_at="2026-10-03T00:00:00.000000+00:00",
        mode="bot_vs_bot",
        white_id=white,
        black_id=black,
        white_name=white,
        black_name=black,
        opening_moves=[],
        moves=[],
        result=types_.GameResult(winner=winner, termination=termination),
    )


def test_expected_score():
    assert ranking.expected_score(1200, 1200) == pytest.approx(0.5)
    assert ranking.expected_score(1400, 1200) == pytest.approx(0.759746, abs=1e-6)
    assert ranking.expected_score(1200, 1400) == pytest.approx(0.240254, abs=1e-6)


def test_player_stats_defaults():
    s = ranking.PlayerStats()
    assert (s.wins, s.draws, s.losses, s.elo, s.games, s.points) == (0, 0, 0, 1200.0, 0, 0.0)
    s2 = ranking.PlayerStats(wins=2, draws=1, losses=3)
    assert (s2.games, s2.points) == (6, 2.5)


def test_win_updates_wdl_and_elo():
    r = ranking.Ranking(None)
    assert r.record_game(rec("mcts", "deep_rl", chess.WHITE)) is True
    w, b = r.stats("mcts"), r.stats("deep_rl")
    assert (w.wins, w.losses, b.wins, b.losses) == (1, 0, 0, 1)
    assert w.elo == pytest.approx(1216.0)
    assert b.elo == pytest.approx(1184.0)


def test_black_win():
    r = ranking.Ranking(None)
    r.record_game(rec("mcts", "deep_rl", chess.BLACK))
    assert r.stats("deep_rl").elo == pytest.approx(1216.0)


def test_draw_between_equals_keeps_elo():
    r = ranking.Ranking(None)
    r.record_game(rec("mcts", "deep_rl", None, T.STALEMATE))
    assert r.stats("mcts").draws == 1 and r.stats("deep_rl").draws == 1
    assert r.stats("mcts").elo == pytest.approx(1200.0)


def test_elo_uses_pre_game_ratings():
    # Ván 2 phải tính E từ rating SAU ván 1 (1216 vs 1184), cập nhật hai bên đồng thời.
    r = ranking.Ranking(None, elo_initial=1200, elo_k=32)
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))  # mcts 1216, deep_rl 1184
    r.record_game(rec("mcts", "deep_rl", None, T.STALEMATE))
    e = ranking.expected_score(1216, 1184)
    assert r.stats("mcts").elo == pytest.approx(1216 + 32 * (0.5 - e))
    assert r.stats("deep_rl").elo == pytest.approx(1184 + 32 * (0.5 - (1 - e)))


def test_custom_k_and_initial():
    r = ranking.Ranking(None, elo_initial=1000, elo_k=16)
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))
    assert r.stats("mcts").elo == pytest.approx(1008.0)
    assert r.stats("unknown").elo == pytest.approx(1000.0)


def test_human_is_ranked():
    r = ranking.Ranking(None)
    assert r.record_game(rec("human", "mcts", chess.WHITE)) is True
    assert r.stats("human").wins == 1


@pytest.mark.parametrize(
    "record",
    [
        rec("mcts", "deep_rl", None, T.ABORTED),
        rec("mcts", "mcts", chess.WHITE),
        rec("random", "mcts", chess.BLACK),
        rec("mcts", "random", chess.WHITE),
    ],
    ids=["aborted", "mirror", "debug_white", "debug_black"],
)
def test_ignored_games(record):
    r = ranking.Ranking(None)
    assert r.record_game(record) is False
    assert r.stats("mcts") == ranking.PlayerStats()


def test_table_contains_known_ids_and_sorted():
    r = ranking.Ranking(None, known_ids=BOTS)
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))
    table = r.table()
    ids = [pid for pid, _ in table]
    assert set(ids) == set(BOTS)
    assert ids[0] == "mcts" and ids[-1] == "deep_rl"
    middle = ids[1:-1]
    assert middle == sorted(middle), "bằng Elo và điểm thì sắp theo id"


def test_persistence_roundtrip(tmp_path):
    path = tmp_path / "ranking.json"
    r = ranking.Ranking(path)
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["players"]["mcts"]["wins"] == 1
    r2 = ranking.Ranking(path)
    assert r2.stats("mcts") == r.stats("mcts")
    assert r2.stats("deep_rl") == r.stats("deep_rl")


def test_no_temp_files_left(tmp_path):
    r = ranking.Ranking(tmp_path / "ranking.json")
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))
    assert [p.name for p in tmp_path.iterdir()] == ["ranking.json"]


def test_reset(tmp_path):
    path = tmp_path / "ranking.json"
    r = ranking.Ranking(path)
    r.record_game(rec("mcts", "deep_rl", chess.WHITE))
    r.reset()
    assert r.stats("mcts") == ranking.PlayerStats()
    assert ranking.Ranking(path).stats("mcts") == ranking.PlayerStats()


def test_corrupt_file_is_backed_up(tmp_path):
    path = tmp_path / "ranking.json"
    path.write_text("{not json", encoding="utf-8")
    r = ranking.Ranking(path)
    assert r.stats("mcts") == ranking.PlayerStats()
    assert (tmp_path / "ranking.json.corrupt").read_text(encoding="utf-8") == "{not json"


def test_missing_parent_directory_is_created(tmp_path):
    path = tmp_path / "data" / "ranking.json"
    ranking.Ranking(path).record_game(rec("mcts", "deep_rl", chess.WHITE))
    assert path.exists()
