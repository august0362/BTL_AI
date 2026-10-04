"""Đặc tả backend/tournament/match_runner.py + records.py — documents/CONTEXT.md §4.6."""

import json
import math
import random
import threading

import chess
import pytest

from tests._helpers import require_module
from tests.tournament.fakes import (
    CrashingPlayer,
    FirstLegalPlayer,
    IllegalPlayer,
    ScriptedPlayer,
    fake_clock,
)

mr = require_module("tournament.match_runner")
records = require_module("tournament.records")
players = require_module("tournament.players")
types_ = require_module("core.types")
Termination = types_.Termination


def fools_mate_runner(**kw):
    white = ScriptedPlayer(["f2f3", "g2g4"], bot_id="w", display_name="White Bot")
    black = ScriptedPlayer(["e7e5", "d8h4"], bot_id="b", display_name="Black Bot")
    return white, black, mr.MatchRunner(white, black, clock=fake_clock(), **kw)


# ----------------------------------------------------------------- ván bình thường


def test_full_game_record():
    white, black, runner = fools_mate_runner()
    rec = runner.play()
    assert isinstance(rec, records.GameRecord)
    assert rec.result.termination == Termination.CHECKMATE
    assert rec.result.winner == chess.BLACK
    assert (rec.white_id, rec.black_id) == ("w", "b")
    assert (rec.white_name, rec.black_name) == ("White Bot", "Black Bot")
    assert rec.mode == "bot_vs_bot"
    assert rec.opening_moves == []
    assert rec.error is None
    assert len(rec.game_id) == 32
    assert [m.uci for m in rec.moves] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert [m.san for m in rec.moves] == ["f3", "e5", "g4", "Qh4#"]
    assert [m.ply for m in rec.moves] == [1, 2, 3, 4]
    assert all(m.think_time_s == pytest.approx(0.5) for m in rec.moves)
    assert not any(m.is_random_opening for m in rec.moves)


def test_pgn_filled():
    _, _, runner = fools_mate_runner()
    pgn = runner.play().pgn
    assert '[White "White Bot"]' in pgn
    assert '[Black "Black Bot"]' in pgn
    assert '[Result "0-1"]' in pgn
    assert "Qh4#" in pgn


def test_players_reset_once():
    white, black, runner = fools_mate_runner()
    runner.play()
    assert white.reset_calls == 1
    assert black.reset_calls == 1


def test_on_move_called_in_order():
    seen = []
    _, _, runner = fools_mate_runner(
        on_move=lambda rec, state: seen.append((rec.uci, state.ply_count))
    )
    runner.play()
    assert seen == [("f2f3", 1), ("e7e5", 2), ("g2g4", 3), ("d8h4", 4)]


def test_search_info_is_copied():
    white, _, runner = fools_mate_runner()
    rec = runner.play()
    assert rec.moves[0].search_info == {"depth": 1}
    white.last_search_info["depth"] = 999
    assert rec.moves[2].search_info == {"depth": 2}


def test_material_eval_and_max_plies():
    white = ScriptedPlayer(["e2e4", "e4d5"])
    black = ScriptedPlayer(["d7d5"])
    rec = mr.MatchRunner(white, black, max_plies=3).play()
    assert rec.result.termination == Termination.MAX_PLIES
    assert rec.moves[1].material_eval == 0.0
    assert rec.moves[2].material_eval == pytest.approx(math.tanh(1 / 8))


def test_eval_scale_passed_through():
    white = ScriptedPlayer(["e2e4", "e4d5"])
    black = ScriptedPlayer(["d7d5"])
    rec = mr.MatchRunner(white, black, max_plies=3, eval_scale=2.0).play()
    assert rec.moves[2].material_eval == pytest.approx(math.tanh(1 / 2))


def test_series_fields_and_mode():
    _, _, runner = fools_mate_runner(mode="human_vs_bot", series_id="s1", series_game_index=2)
    rec = runner.play()
    assert (rec.mode, rec.series_id, rec.series_game_index) == ("human_vs_bot", "s1", 2)


# ----------------------------------------------------------------- khai cuộc


def test_generate_random_opening():
    op = mr.generate_random_opening(4, random.Random(7))
    assert len(op) == 4
    board = chess.Board()
    for u in op:
        move = chess.Move.from_uci(u)
        assert move in board.legal_moves
        board.push(move)
    assert not board.is_game_over()
    assert mr.generate_random_opening(4, random.Random(7)) == op
    assert mr.generate_random_opening(0, random.Random(7)) == []


def test_random_opening_applied():
    white, black = FirstLegalPlayer("w"), FirstLegalPlayer("b")
    rec = mr.MatchRunner(
        white, black, random_opening_plies=2, max_plies=6, rng=random.Random(3)
    ).play()
    assert len(rec.opening_moves) == 2
    assert [m.uci for m in rec.moves[:2]] == rec.opening_moves
    assert all(m.is_random_opening and m.think_time_s == 0 for m in rec.moves[:2])
    assert not any(m.is_random_opening for m in rec.moves[2:])
    assert white.select_calls + black.select_calls == len(rec.moves) - 2


def test_random_opening_deterministic_with_seed():
    def run():
        r = mr.MatchRunner(
            FirstLegalPlayer(),
            FirstLegalPlayer(),
            random_opening_plies=2,
            max_plies=4,
            rng=random.Random(11),
        )
        return r.play().opening_moves

    assert run() == run()


def test_explicit_opening_moves_override_random():
    rec = mr.MatchRunner(
        FirstLegalPlayer(),
        FirstLegalPlayer(),
        opening_moves=["d2d4", "d7d5"],
        random_opening_plies=4,
        max_plies=4,
    ).play()
    assert rec.opening_moves == ["d2d4", "d7d5"]
    assert [m.uci for m in rec.moves[:2]] == ["d2d4", "d7d5"]


# ----------------------------------------------------------------- hủy ván


def test_request_stop_from_on_move():
    holder = {}

    def on_move(rec, state):
        if state.ply_count == 2:
            holder["runner"].request_stop()

    runner = mr.MatchRunner(FirstLegalPlayer(), FirstLegalPlayer(), on_move=on_move)
    holder["runner"] = runner
    rec = runner.play()
    assert rec.result.termination == Termination.ABORTED
    assert rec.result.winner is None
    assert len(rec.moves) == 2
    assert rec.error is None


def test_crashing_bot_aborts_without_raising():
    rec = mr.MatchRunner(CrashingPlayer("c"), FirstLegalPlayer()).play()
    assert rec.result.termination == Termination.ABORTED
    assert "c" in rec.error and "boom" in rec.error


def test_illegal_move_aborts():
    rec = mr.MatchRunner(FirstLegalPlayer(), IllegalPlayer("bad")).play()
    assert rec.result.termination == Termination.ABORTED
    assert "bad" in rec.error
    assert len(rec.moves) == 1


def test_human_vs_bot_in_thread():
    human = players.HumanPlayer()
    bot = ScriptedPlayer(["f2f3", "g2g4"])
    runner = mr.MatchRunner(bot, human, mode="human_vs_bot")
    out = []
    t = threading.Thread(target=lambda: out.append(runner.play()))
    t.start()
    for u in ["e7e4", "e7e5", "d8h4"]:  # e7e4 không hợp lệ -> bị bỏ qua
        human.submit_move(chess.Move.from_uci(u))
    t.join(5)
    assert not t.is_alive()
    assert out[0].result.winner == chess.BLACK
    assert out[0].black_id == "human"


def test_request_stop_releases_waiting_human():
    human = players.HumanPlayer()
    runner = mr.MatchRunner(human, FirstLegalPlayer(), mode="human_vs_bot")
    out = []
    t = threading.Thread(target=lambda: out.append(runner.play()))
    t.start()
    t.join(0.2)
    runner.request_stop()
    t.join(5)
    assert not t.is_alive()
    assert out[0].result.termination == Termination.ABORTED
    assert out[0].moves == []


def test_pause_and_resume():
    moves = []
    runner = mr.MatchRunner(
        FirstLegalPlayer(), FirstLegalPlayer(), max_plies=4, on_move=lambda r, s: moves.append(r)
    )
    runner.pause()
    out = []
    t = threading.Thread(target=lambda: out.append(runner.play()))
    t.start()
    t.join(0.3)
    assert t.is_alive() and moves == [], "đang pause thì không được đi"
    runner.resume()
    t.join(5)
    assert len(out[0].moves) == 4


# ----------------------------------------------------------------- JSON


def test_record_json_roundtrip():
    _, _, runner = fools_mate_runner(series_id="s", series_game_index=1)
    rec = runner.play()
    data = rec.to_json()
    json.dumps(data)  # phải serialize được
    assert data["result"]["winner"] == "black"
    assert data["result"]["termination"] == "checkmate"
    assert records.GameRecord.from_json(json.loads(json.dumps(data))) == rec


def test_aborted_record_json_roundtrip():
    rec = mr.MatchRunner(CrashingPlayer(), FirstLegalPlayer()).play()
    data = json.loads(json.dumps(rec.to_json()))
    assert data["result"]["winner"] is None
    assert records.GameRecord.from_json(data) == rec
