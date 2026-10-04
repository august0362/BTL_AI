"""Đặc tả backend/core/material.py — documents/CONTEXT.md §4.5."""

import math

import chess
import pytest

from tests._helpers import require_module

material = require_module("core.material")

NO_BLACK_QUEEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
NO_WHITE_A_ROOK = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/1NBQKBNR w Kkq - 0 1"
LONE_BLACK_KING = "4k3/8/8/8/8/8/PPPPPPPP/RNBQKBNR w KQ - 0 1"


def test_piece_values():
    assert material.PIECE_VALUES == {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }


@pytest.mark.parametrize(
    ("fen", "expected"),
    [(chess.STARTING_FEN, 0), (NO_BLACK_QUEEN, 9), (NO_WHITE_A_ROOK, -5), (LONE_BLACK_KING, 39)],
)
def test_material_diff(fen, expected):
    assert material.material_diff(chess.Board(fen)) == expected


def test_eval_bar_value_formula():
    assert material.eval_bar_value(chess.Board()) == 0.0
    assert material.eval_bar_value(chess.Board(NO_BLACK_QUEEN)) == pytest.approx(math.tanh(9 / 8))
    assert material.eval_bar_value(chess.Board(NO_WHITE_A_ROOK)) == pytest.approx(math.tanh(-5 / 8))


def test_eval_bar_value_custom_scale():
    v = material.eval_bar_value(chess.Board(NO_BLACK_QUEEN), scale=4.0)
    assert v == pytest.approx(math.tanh(9 / 4))


def test_eval_bar_value_bounded():
    v = material.eval_bar_value(chess.Board(LONE_BLACK_KING))
    assert 0.99 < v <= 1.0


def test_does_not_mutate_board():
    b = chess.Board(NO_BLACK_QUEEN)
    material.material_diff(b)
    material.eval_bar_value(b)
    assert b.fen() == NO_BLACK_QUEEN
