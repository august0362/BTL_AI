"""Đặc tả backend/tournament/players.py — documents/CONTEXT.md §4.6."""

import threading

import chess
import pytest

from tests._helpers import require_module

players = require_module("tournament.players")


def test_human_identity():
    h = players.HumanPlayer("Tôi")
    assert h.bot_id == players.HUMAN_ID == "human"
    assert h.display_name == "Tôi"
    assert players.HumanPlayer().display_name == "Human"


def test_select_move_returns_submitted_move():
    h = players.HumanPlayer()
    h.submit_move(chess.Move.from_uci("e2e4"))
    assert h.select_move(chess.Board()) == chess.Move.from_uci("e2e4")


def test_illegal_submissions_are_ignored():
    h = players.HumanPlayer()
    h.submit_move(chess.Move.from_uci("e2e5"))
    h.submit_move(chess.Move.from_uci("g1f3"))
    assert h.select_move(chess.Board()) == chess.Move.from_uci("g1f3")


def test_select_move_blocks_until_submitted():
    h = players.HumanPlayer()
    out = []
    t = threading.Thread(target=lambda: out.append(h.select_move(chess.Board())))
    t.start()
    t.join(0.2)
    assert t.is_alive(), "phải chờ người chơi"
    h.submit_move(chess.Move.from_uci("d2d4"))
    t.join(2)
    assert out == [chess.Move.from_uci("d2d4")]


def test_cancel_unblocks_with_match_aborted():
    h = players.HumanPlayer()
    errors = []

    def wait():
        try:
            h.select_move(chess.Board())
        except players.MatchAborted as e:
            errors.append(e)

    t = threading.Thread(target=wait)
    t.start()
    t.join(0.1)
    h.cancel()
    t.join(2)
    assert not t.is_alive()
    assert len(errors) == 1


def test_reset_clears_queue_and_cancel():
    h = players.HumanPlayer()
    h.submit_move(chess.Move.from_uci("e2e4"))
    h.cancel()
    h.reset()
    h.submit_move(chess.Move.from_uci("d2d4"))
    assert h.select_move(chess.Board()) == chess.Move.from_uci("d2d4")


def test_match_aborted_is_exception():
    assert issubclass(players.MatchAborted, Exception)
    with pytest.raises(players.MatchAborted):
        raise players.MatchAborted()
