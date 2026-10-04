"""Đặc tả frontend/gui/board_geometry.py — documents/CONTEXT.md §5.8."""

import chess
import pytest

from tests._helpers import require_module

geo = require_module("gui.board_geometry")


def test_constants():
    assert (geo.BOARD_SIZE, geo.SQUARE_SIZE) == (640, 80)


@pytest.mark.parametrize(
    ("xy", "square"),
    [
        ((0, 0), chess.A8),
        ((79, 79), chess.A8),
        ((80, 0), chess.B8),
        ((639, 639), chess.H1),
        ((0, 639), chess.A1),
        ((330, 330), chess.E4),
    ],
)
def test_square_at_white_view(xy, square):
    assert geo.square_at(*xy) == square


@pytest.mark.parametrize(
    ("xy", "square"),
    [((0, 0), chess.H1), ((639, 639), chess.A8), ((0, 639), chess.H8), ((330, 330), chess.D5)],
)
def test_square_at_flipped(xy, square):
    assert geo.square_at(*xy, flipped=True) == square


@pytest.mark.parametrize("xy", [(640, 0), (0, 640), (-1, 10), (10, -0.5), (700, 300)])
def test_square_at_outside_board(xy):
    assert geo.square_at(*xy) is None


def test_square_origin():
    assert geo.square_origin(chess.A8) == (0, 0)
    assert geo.square_origin(chess.H1) == (560, 560)
    assert geo.square_origin(chess.E4) == (320, 320)
    assert geo.square_origin(chess.A8, flipped=True) == (560, 560)
    assert geo.square_origin(chess.H1, flipped=True) == (0, 0)


@pytest.mark.parametrize("flipped", [False, True])
def test_roundtrip_all_squares(flipped):
    for sq in chess.SQUARES:
        x, y = geo.square_origin(sq, flipped=flipped)
        assert geo.square_at(x + 40, y + 40, flipped=flipped) == sq
