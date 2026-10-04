"""Đặc tả backend/tournament/records.py — documents/CONTEXT.md §4.6."""

import json

import chess

from tests._helpers import require_module

records = require_module("tournament.records")
types_ = require_module("core.types")


def make(winner=chess.WHITE, termination=None, **kw):
    termination = termination or types_.Termination.CHECKMATE
    move = types_.MoveRecord(
        ply=1,
        uci="e2e4",
        san="e4",
        think_time_s=0.25,
        search_info={"depth": 2},
        material_eval=0.0,
        is_random_opening=False,
    )
    return records.GameRecord(
        game_id="abc",
        started_at="2026-10-03T00:00:00.000000+00:00",
        mode="human_vs_bot",
        white_id="human",
        black_id="mcts",
        white_name="Player",
        black_name="MCTS",
        opening_moves=[],
        moves=[move],
        result=types_.GameResult(winner=winner, termination=termination),
        **kw,
    )


def test_defaults():
    r = make()
    assert (r.pgn, r.series_id, r.series_game_index, r.error) == ("", None, None, None)


def test_json_shape():
    d = make(winner=chess.BLACK).to_json()
    json.dumps(d)
    assert d["result"] == {"winner": "black", "termination": "checkmate"}
    assert d["moves"][0]["uci"] == "e2e4"


def test_roundtrip_all_winners():
    for winner in (chess.WHITE, chess.BLACK, None):
        r = make(winner=winner, series_id="s", series_game_index=3, error=None, pgn="1. e4 *")
        assert records.GameRecord.from_json(json.loads(json.dumps(r.to_json()))) == r


def test_roundtrip_aborted_with_error():
    r = make(winner=None, termination=types_.Termination.ABORTED, error="mcts: boom")
    assert records.GameRecord.from_json(r.to_json()) == r
