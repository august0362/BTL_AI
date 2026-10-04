"""Đặc tả frontend/gui/move_input.py (click-to-move) — documents/CONTEXT.md §5.3, §5.8."""

import chess
import pytest

from tests._helpers import require_module

mi = require_module("gui.move_input")

W = chess.WHITE
PROMO_FEN = "8/P6k/8/8/8/8/8/K7 w - - 0 1"


def click(inp, board, square, color=W):
    return inp.click(board, square, color)


def test_select_own_piece():
    inp, b = mi.MoveInput(), chess.Board()
    r = click(inp, b, chess.E2)
    assert (r.kind, r.square) == ("select", chess.E2)
    assert inp.selected == chess.E2
    assert inp.legal_targets(b) == {chess.E3, chess.E4}


def test_click_empty_or_enemy_without_selection():
    inp, b = mi.MoveInput(), chess.Board()
    assert click(inp, b, chess.E4).kind == "none"
    assert click(inp, b, chess.E7).kind == "none"
    assert inp.selected is None


def test_piece_without_legal_moves_not_selectable():
    inp, b = mi.MoveInput(), chess.Board()
    assert click(inp, b, chess.A1).kind == "none"  # Xe a1 bị chặn


def test_move():
    inp, b = mi.MoveInput(), chess.Board()
    click(inp, b, chess.G1)
    r = click(inp, b, chess.F3)
    assert (r.kind, r.move) == ("move", chess.Move.from_uci("g1f3"))
    assert inp.selected is None


def test_click_same_square_deselects():
    inp, b = mi.MoveInput(), chess.Board()
    click(inp, b, chess.E2)
    assert click(inp, b, chess.E2).kind == "deselect"
    assert inp.selected is None


def test_switch_selection_to_other_own_piece():
    inp, b = mi.MoveInput(), chess.Board()
    click(inp, b, chess.E2)
    r = click(inp, b, chess.D2)
    assert (r.kind, r.square) == ("select", chess.D2)


def test_illegal_target_deselects():
    inp, b = mi.MoveInput(), chess.Board()
    click(inp, b, chess.E2)
    assert click(inp, b, chess.E5).kind == "deselect"
    assert inp.selected is None


def test_click_outside_board():
    inp, b = mi.MoveInput(), chess.Board()
    assert click(inp, b, None).kind == "none"
    click(inp, b, chess.E2)
    assert click(inp, b, None).kind == "deselect"


def test_not_players_turn():
    inp, b = mi.MoveInput(), chess.Board()
    assert click(inp, b, chess.E7, color=chess.BLACK).kind == "none"
    assert click(inp, b, chess.E2, color=chess.BLACK).kind == "none"


def test_black_player():
    inp, b = mi.MoveInput(), chess.Board()
    b.push_san("e4")
    click(inp, b, chess.E7, color=chess.BLACK)
    r = click(inp, b, chess.E5, color=chess.BLACK)
    assert r.move == chess.Move.from_uci("e7e5")


def test_promotion_flow():
    inp, b = mi.MoveInput(), chess.Board(PROMO_FEN)
    click(inp, b, chess.A7)
    r = click(inp, b, chess.A8)
    assert r.kind == "promotion"
    assert {m.promotion for m in r.promotion_moves} == {
        chess.QUEEN,
        chess.ROOK,
        chess.BISHOP,
        chess.KNIGHT,
    }
    assert inp.choose_promotion(chess.KNIGHT) == chess.Move.from_uci("a7a8n")
    assert inp.selected is None


def test_choose_promotion_without_pending_raises():
    with pytest.raises(ValueError):
        mi.MoveInput().choose_promotion(chess.QUEEN)


def test_clear():
    inp, b = mi.MoveInput(), chess.Board()
    click(inp, b, chess.E2)
    inp.clear()
    assert inp.selected is None
    assert inp.legal_targets(b) == set()
