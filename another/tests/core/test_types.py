"""Đặc tả backend/core/types.py — documents/CONTEXT.md §4.3."""

import dataclasses

import chess
import pytest

from tests._helpers import require_module

types_ = require_module("core.types")
Termination = types_.Termination
GameResult = types_.GameResult
MoveRecord = types_.MoveRecord


def test_termination_values_are_stable_strings():
    # Giá trị được ghi vào JSON lịch sử ván => không được đổi tùy tiện.
    assert {t.name: t.value for t in Termination} == {
        "CHECKMATE": "checkmate",
        "STALEMATE": "stalemate",
        "INSUFFICIENT_MATERIAL": "insufficient_material",
        "THREEFOLD_REPETITION": "threefold_repetition",
        "FIFTY_MOVES": "fifty_moves",
        "MAX_PLIES": "max_plies",
        "ABORTED": "aborted",
    }
    assert Termination("checkmate") is Termination.CHECKMATE


def test_score_for_win():
    r = GameResult(winner=chess.WHITE, termination=Termination.CHECKMATE)
    assert r.score_for(chess.WHITE) == 1.0
    assert r.score_for(chess.BLACK) == 0.0


def test_score_for_draw():
    r = GameResult(winner=None, termination=Termination.STALEMATE)
    assert r.score_for(chess.WHITE) == 0.5
    assert r.score_for(chess.BLACK) == 0.5


def test_score_for_aborted_raises():
    r = GameResult(winner=None, termination=Termination.ABORTED)
    with pytest.raises(ValueError):
        r.score_for(chess.WHITE)


def test_game_result_is_frozen():
    r = GameResult(winner=None, termination=Termination.MAX_PLIES)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.winner = chess.WHITE


def test_move_record_fields():
    m = MoveRecord(
        ply=1,
        uci="e2e4",
        san="e4",
        think_time_s=0.01,
        search_info={"depth": 3},
        material_eval=0.0,
        is_random_opening=False,
    )
    assert m.uci == "e2e4"
    with pytest.raises(dataclasses.FrozenInstanceError):
        m.ply = 2


def test_error_types_exist():
    assert issubclass(types_.IllegalMoveError, ValueError)
    assert issubclass(types_.GameOverError, RuntimeError)
