"""Đặc tả backend/core/game_state.py — documents/CONTEXT.md §4.3, §4.4."""

import chess
import pytest

from tests._helpers import require_module

gs_mod = require_module("core.game_state")
types_ = require_module("core.types")
GameState = gs_mod.GameState
Termination = types_.Termination

FOOLS_MATE = ["f2f3", "e7e5", "g2g4", "d8h4"]
KNIGHT_SHUFFLE = ["g1f3", "g8f6", "f3g1", "f6g8"]


def play(gs, ucis):
    for u in ucis:
        gs.push(chess.Move.from_uci(u))
    return gs


# ----------------------------------------------------------------- cơ bản


def test_starts_from_standard_position():
    gs = GameState()
    assert gs.fen == chess.STARTING_FEN
    assert gs.starting_fen == chess.STARTING_FEN
    assert gs.turn == chess.WHITE
    assert gs.ply_count == 0
    assert len(gs.legal_moves()) == 20
    assert not gs.is_over()
    assert gs.result() is None


def test_custom_fen():
    fen = "4k3/8/8/8/8/8/8/R3K3 w Q - 0 1"
    gs = GameState(fen=fen)
    assert gs.fen == fen
    assert gs.starting_fen == fen


def test_push_returns_san_and_advances():
    gs = GameState()
    assert gs.push(chess.Move.from_uci("e2e4")) == "e4"
    assert gs.turn == chess.BLACK
    assert gs.ply_count == 1


def test_board_property_returns_copy():
    gs = GameState()
    b = gs.board
    assert isinstance(b, chess.Board)
    b.push_san("e4")
    assert gs.ply_count == 0
    assert gs.fen == chess.STARTING_FEN


def test_board_copy_keeps_move_stack():
    # Bot cần lịch sử để tự phát hiện lặp thế cờ.
    gs = play(GameState(), ["e2e4", "e7e5"])
    assert [m.uci() for m in gs.board.move_stack] == ["e2e4", "e7e5"]


def test_illegal_move_raises_and_state_unchanged():
    gs = GameState()
    with pytest.raises(types_.IllegalMoveError):
        gs.push(chess.Move.from_uci("e2e5"))
    assert gs.ply_count == 0
    assert gs.fen == chess.STARTING_FEN


def test_push_after_game_over_raises():
    gs = play(GameState(), FOOLS_MATE)
    with pytest.raises(types_.GameOverError):
        gs.push(chess.Move.from_uci("e1f2"))


def test_promotion_requires_piece():
    gs = GameState(fen="8/P6k/8/8/8/8/8/K7 w - - 0 1")
    with pytest.raises(types_.IllegalMoveError):
        gs.push(chess.Move.from_uci("a7a8"))
    assert gs.push(chess.Move.from_uci("a7a8q")) == "a8=Q"


def test_special_moves_are_legal():
    castling = GameState(fen="r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert chess.Move.from_uci("e1g1") in castling.legal_moves()
    assert chess.Move.from_uci("e1c1") in castling.legal_moves()
    en_passant = GameState(fen="4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 2")
    assert chess.Move.from_uci("e5d6") in en_passant.legal_moves()


def test_no_undo_api():
    # Yêu cầu sản phẩm: không có Undo.
    assert not hasattr(GameState, "undo")
    assert not hasattr(GameState, "pop")


# ----------------------------------------------------------------- kết thúc ván


def test_checkmate_black_wins():
    gs = play(GameState(), FOOLS_MATE)
    assert gs.is_over()
    r = gs.result()
    assert r.termination == Termination.CHECKMATE
    assert r.winner == chess.BLACK


def test_stalemate_on_init():
    gs = GameState(fen="7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert gs.is_over()
    assert gs.result().termination == Termination.STALEMATE
    assert gs.result().winner is None


def test_stalemate_after_move():
    gs = GameState(fen="7k/8/6K1/8/8/8/5Q2/8 w - - 0 1")
    gs.push(chess.Move.from_uci("f2f7"))
    assert gs.result().termination == Termination.STALEMATE


def test_insufficient_material_on_init():
    gs = GameState(fen="8/8/8/4k3/8/8/8/4K3 w - - 0 1")
    assert gs.result().termination == Termination.INSUFFICIENT_MATERIAL


def test_insufficient_material_after_capture():
    gs = GameState(fen="8/8/8/4k3/8/8/4p3/4K3 w - - 0 1")
    gs.push(chess.Move.from_uci("e1e2"))
    assert gs.result().termination == Termination.INSUFFICIENT_MATERIAL


def test_threefold_ends_exactly_on_third_occurrence():
    # Thế cờ ban đầu xuất hiện ở ply 0, 4, 8. Phải kết thúc ĐÚNG ở ply 8,
    # KHÔNG kết thúc sớm ở ply 7. Lưu ý: python-chess outcome(claim_draw=True)
    # kết thúc sớm ở ply 7 => không dùng hàm đó cho luật này.
    gs = play(GameState(), KNIGHT_SHUFFLE + KNIGHT_SHUFFLE[:3])
    assert not gs.is_over()
    gs.push(chess.Move.from_uci(KNIGHT_SHUFFLE[3]))
    assert gs.is_over()
    assert gs.result().termination == Termination.THREEFOLD_REPETITION
    assert gs.result().winner is None


def test_threefold_disabled_when_claim_draw_false():
    gs = play(GameState(claim_draw=False), KNIGHT_SHUFFLE * 2)
    assert not gs.is_over()


def test_fifty_move_rule_at_halfmove_100():
    gs = GameState(fen="8/8/8/4k3/8/8/2R5/4K3 w - - 99 80")
    assert not gs.is_over()
    gs.push(chess.Move.from_uci("c2c3"))
    assert gs.result().termination == Termination.FIFTY_MOVES


def test_capture_resets_fifty_move_counter():
    gs = GameState(fen="8/8/8/4k3/8/2p5/2R5/4K3 w - - 99 80")
    gs.push(chess.Move.from_uci("c2c3"))
    assert not gs.is_over()


def test_fifty_move_disabled_when_claim_draw_false():
    gs = GameState(fen="8/8/8/4k3/8/8/2R5/4K3 w - - 99 80", claim_draw=False)
    gs.push(chess.Move.from_uci("c2c3"))
    assert not gs.is_over()


def test_checkmate_beats_fifty_move_rule():
    gs = GameState(fen="7k/8/6K1/8/8/8/8/R7 w - - 99 80")
    gs.push(chess.Move.from_uci("a1a8"))
    assert gs.result().termination == Termination.CHECKMATE
    assert gs.result().winner == chess.WHITE


def test_max_plies():
    gs = play(GameState(max_plies=4), ["e2e4", "e7e5", "g1f3"])
    assert not gs.is_over()
    gs.push(chess.Move.from_uci("b8c6"))
    assert gs.result().termination == Termination.MAX_PLIES
    assert gs.result().winner is None


def test_checkmate_beats_max_plies():
    gs = play(GameState(max_plies=4), FOOLS_MATE)
    assert gs.result().termination == Termination.CHECKMATE


def test_max_plies_counts_from_gamestate_creation():
    # FEN có fullmove 80 nhưng ply_count tính từ lúc tạo GameState.
    gs = GameState(fen="8/8/8/4k3/8/8/2R5/4K3 w - - 0 80", max_plies=2)
    play(gs, ["c2c3", "e5e4"])
    assert gs.result().termination == Termination.MAX_PLIES


def test_max_plies_must_be_positive():
    with pytest.raises(ValueError):
        GameState(max_plies=0)


# ----------------------------------------------------------------- PGN


def test_pgn_of_finished_game():
    gs = play(GameState(), FOOLS_MATE)
    pgn = gs.to_pgn({"White": "Bot A", "Black": "Bot B"})
    assert '[White "Bot A"]' in pgn
    assert '[Black "Bot B"]' in pgn
    assert '[Result "0-1"]' in pgn
    assert "1. f3 e5 2. g4 Qh4#" in pgn


def test_pgn_of_unfinished_game():
    gs = play(GameState(), ["e2e4"])
    pgn = gs.to_pgn({})
    assert '[Result "*"]' in pgn
    assert "1. e4" in pgn


def test_pgn_of_draw_and_custom_fen():
    fen = "7k/8/6K1/8/8/8/5Q2/8 w - - 0 1"
    gs = GameState(fen=fen)
    gs.push(chess.Move.from_uci("f2f7"))
    pgn = gs.to_pgn({})
    assert '[Result "1/2-1/2"]' in pgn
    assert f'[FEN "{fen}"]' in pgn
