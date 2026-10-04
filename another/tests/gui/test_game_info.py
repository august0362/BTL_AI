"""Đặc tả frontend/gui/game_info.py (số liệu cho panel) — documents/CONTEXT.md §5.4, §5.8."""

from types import SimpleNamespace

import chess
import pytest

from tests._helpers import require_module

info = require_module("gui.game_info")


def mv(ply, t, rnd=False):
    return SimpleNamespace(ply=ply, think_time_s=t, is_random_opening=rnd)


def test_no_captures_at_start():
    assert info.captured_pieces(chess.Board()) == {chess.WHITE: [], chess.BLACK: []}


def test_captured_sorted_by_value():
    # Trắng mất Hậu + 1 Tốt; Đen mất 1 Mã + 1 Xe.
    b = chess.Board("r1bqkbn1/pppppppp/8/8/8/8/1PPPPPPP/RNB1KBNR w KQq - 0 1")
    assert info.captured_pieces(b) == {
        chess.WHITE: [chess.QUEEN, chess.PAWN],
        chess.BLACK: [chess.ROOK, chess.KNIGHT],
    }


def test_promotion_never_negative():
    # Trắng có 2 Hậu (phong cấp) và thiếu 1 Tốt => mất 1 Tốt, không có số âm.
    b = chess.Board("4k3/8/8/8/8/8/1PPPPPPP/QNBQKBNR w K - 0 1")
    assert info.captured_pieces(b)[chess.WHITE] == [chess.ROOK, chess.PAWN]


def test_think_time_summary():
    moves = [mv(1, 0, True), mv(2, 0, True), mv(3, 1.0), mv(4, 3.0), mv(5, 2.0)]
    s = info.think_time_summary(moves)
    assert s[chess.WHITE] == pytest.approx((2.0, 1.5))
    assert s[chess.BLACK] == pytest.approx((3.0, 3.0))


def test_think_time_summary_empty():
    s = info.think_time_summary([mv(1, 0, True)])
    assert s == {chess.WHITE: (None, None), chess.BLACK: (None, None)}
