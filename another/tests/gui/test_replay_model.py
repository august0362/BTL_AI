"""Tests for the pygame-independent replay model."""

import chess

from core.types import GameResult, MoveRecord, Termination
from gui.replay_model import ReplayModel
from tournament.records import GameRecord


def make_record(ucis: list[str]) -> GameRecord:
    board = chess.Board()
    moves = []
    for ply, uci in enumerate(ucis, start=1):
        move = chess.Move.from_uci(uci)
        moves.append(MoveRecord(ply, uci, board.san(move), 0.0, {}, 0.0, False))
        board.push(move)
    return GameRecord(
        game_id="game",
        started_at="",
        mode="bot_vs_bot",
        white_id="white",
        black_id="black",
        white_name="White",
        black_name="Black",
        opening_moves=[],
        moves=moves,
        result=GameResult(None, Termination.ABORTED),
    )


def test_navigation_and_board_are_copies_with_move_stack() -> None:
    model = ReplayModel(make_record(["e2e4", "e7e5", "g1f3"]))

    assert model.index == 0
    assert model.length == 3
    assert model.last_move is None
    assert model.current_move is None
    assert model.board.fen() == chess.STARTING_FEN
    assert model.next()
    assert model.current_move is not None and model.current_move.uci == "e2e4"
    assert model.last_move == chess.Move.from_uci("e2e4")
    board = model.board
    assert len(board.move_stack) == 1
    board.push_san("c5")
    assert model.board.fen() != board.fen()
    assert model.prev()
    assert not model.prev()
    model.seek(-10)
    assert model.index == 0
    model.seek(100)
    assert model.index == model.length
    assert not model.next()


def test_seek_clamps_and_delay_is_clamped() -> None:
    model = ReplayModel(make_record(["e2e4"]))
    model.seek(-1)
    assert model.index == 0
    model.seek(2)
    assert model.index == 1
    model.delay_ms = 0
    assert model.delay_ms == 100
    model.delay_ms = 9000
    assert model.delay_ms == 5000


def test_playback_advances_and_auto_pauses_at_end() -> None:
    model = ReplayModel(make_record(["e2e4", "e7e5"]))
    model.delay_ms = 100
    model.play(1000)
    assert not model.tick(1099)
    assert model.tick(1100)
    assert model.playing
    assert model.tick(1200)
    assert model.index == 2
    assert not model.playing
    assert not model.tick(1300)


def test_play_at_end_restarts_from_start() -> None:
    model = ReplayModel(make_record(["e2e4", "e7e5"]))
    model.last()
    model.play(500)
    assert model.index == 0
    assert model.playing
