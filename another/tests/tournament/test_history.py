"""Đặc tả backend/tournament/history.py — documents/CONTEXT.md §4.8."""

from tests._helpers import require_module

history = require_module("tournament.history")
records = require_module("tournament.records")
types_ = require_module("core.types")


def rec(i, pgn="1. e4 *"):
    return records.GameRecord(
        game_id=f"g{i:02d}",
        started_at=f"2026-10-03T00:00:{i:02d}.000000+00:00",
        mode="bot_vs_bot",
        white_id="mcts",
        black_id="deep_rl",
        white_name="MCTS",
        black_name="Deep RL",
        opening_moves=[],
        moves=[],
        result=types_.GameResult(winner=None, termination=types_.Termination.MAX_PLIES),
        pgn=pgn,
    )


def test_directory_created(tmp_path):
    d = tmp_path / "history"
    history.History(d)
    assert d.is_dir()


def test_save_and_list_newest_first(tmp_path):
    h = history.History(tmp_path)
    for i in (1, 3, 2):
        assert h.save(rec(i)) == tmp_path / f"g{i:02d}.json"
    assert [r.game_id for r in h.list()] == ["g03", "g02", "g01"]


def test_prunes_oldest(tmp_path):
    h = history.History(tmp_path, max_games=3)
    for i in range(1, 6):
        h.save(rec(i))
    assert [r.game_id for r in h.list()] == ["g05", "g04", "g03"]
    assert sorted(p.name for p in tmp_path.glob("*.json")) == ["g03.json", "g04.json", "g05.json"]


def test_load_roundtrip(tmp_path):
    h = history.History(tmp_path)
    r = rec(1)
    h.save(r)
    assert h.load("g01") == r


def test_export_pgn(tmp_path):
    h = history.History(tmp_path / "h")
    h.save(rec(1, pgn='[Event "x"]\n\n1. e4 *'))
    out = h.export_pgn("g01", tmp_path / "out.pgn")
    assert out == tmp_path / "out.pgn"
    assert out.read_text(encoding="utf-8") == '[Event "x"]\n\n1. e4 *'


def test_corrupt_files_skipped(tmp_path):
    h = history.History(tmp_path)
    h.save(rec(1))
    (tmp_path / "broken.json").write_text("{oops", encoding="utf-8")
    assert [r.game_id for r in h.list()] == ["g01"]
