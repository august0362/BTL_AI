"""Đặc tả frontend/gui/controller.py — documents/CONTEXT.md §5.9."""

import random
import time

import chess
import pytest

from tests._helpers import require_module
from tests.tournament.fakes import FirstLegalPlayer, FoolsMatePlayer

controller = require_module("gui.controller")
players = require_module("tournament.players")
ranking_mod = require_module("tournament.ranking")
history_mod = require_module("tournament.history")
types_ = require_module("core.types")

CONFIG = {
    "game": {"random_opening_plies": 2, "max_plies": 300, "claim_draw": True},
    "eval_bar": {"scale": 8.0},
    "ui": {"bot_move_delay_ms": 0},
}


def wait_until(pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def human_vs_bot(human_color=chess.WHITE, bot=None, **kw):
    human = players.HumanPlayer()
    bot = bot or FirstLegalPlayer("bot")
    white, black = (human, bot) if human_color == chess.WHITE else (bot, human)
    return controller.GameController(white, black, mode="human_vs_bot", config=CONFIG, **kw)


def test_human_move_then_bot_reply():
    c = human_vs_bot()
    assert c.human_color() == chess.WHITE
    c.start()
    assert wait_until(lambda: c.snapshot().waiting_for_human)
    snap = c.snapshot()
    assert not snap.thinking
    assert snap.moves == () and snap.board.fen() == chess.STARTING_FEN, (
        "Người vs Bot: không khai cuộc ngẫu nhiên"
    )
    c.submit_human_move(chess.Move.from_uci("e2e4"))
    assert wait_until(lambda: len(c.snapshot().moves) == 2)
    snap = c.snapshot()
    assert snap.moves[0].uci == "e2e4"
    assert snap.board.turn == chess.WHITE
    assert (snap.game_index, snap.n_games, snap.finished) == (1, 1, False)
    c.stop()
    assert c.join(5)
    assert c.snapshot().finished


def test_snapshot_board_is_a_copy():
    c = human_vs_bot()
    c.start()
    snap = c.snapshot()
    snap.board.push_san("e4")
    assert c.snapshot().board.fen() == chess.STARTING_FEN
    c.stop()
    c.join(5)


def test_human_as_black_bot_moves_first():
    c = human_vs_bot(human_color=chess.BLACK)
    assert c.human_color() == chess.BLACK
    c.start()
    assert wait_until(lambda: c.snapshot().waiting_for_human)
    assert len(c.snapshot().moves) == 1
    assert not c.snapshot().thinking
    c.stop()
    c.join(5)


def test_start_twice_raises():
    c = human_vs_bot()
    c.start()
    with pytest.raises(RuntimeError):
        c.start()
    c.stop()
    c.join(5)


def test_human_vs_bot_requires_single_game():
    with pytest.raises(ValueError):
        human_vs_bot(n_games=3)


def test_finished_game_saved_to_history_and_ranking(tmp_path):
    rk = ranking_mod.Ranking(tmp_path / "ranking.json")
    hs = history_mod.History(tmp_path / "history")
    # Người cầm đen chiếu hết nhanh (bot trắng tự sát f3, g4).
    c = human_vs_bot(human_color=chess.BLACK, bot=FoolsMatePlayer("mcts"), ranking=rk, history=hs)
    c.start()
    assert wait_until(lambda: c.snapshot().waiting_for_human)
    assert len(c.snapshot().moves) == 1
    c.submit_human_move(chess.Move.from_uci("e7e5"))
    c.submit_human_move(chess.Move.from_uci("d8h4"))
    assert c.join(5)
    snap = c.snapshot()
    assert snap.finished
    assert len(snap.finished_games) == 1
    assert snap.finished_games[0].result.winner == chess.BLACK
    assert rk.stats("human").wins == 1
    assert [r.game_id for r in hs.list()] == [snap.finished_games[0].game_id]


def test_stop_saves_aborted_game_without_ranking(tmp_path):
    rk = ranking_mod.Ranking(tmp_path / "ranking.json")
    hs = history_mod.History(tmp_path / "history")
    c = human_vs_bot(ranking=rk, history=hs)
    c.start()
    c.stop()
    assert c.join(5)
    games = hs.list()
    assert len(games) == 1
    assert games[0].result.termination == types_.Termination.ABORTED
    assert rk.stats("human") == ranking_mod.PlayerStats()


def test_bot_vs_bot_series():
    a, b = FoolsMatePlayer("A"), FoolsMatePlayer("B")
    cfg = {**CONFIG, "game": {**CONFIG["game"], "random_opening_plies": 0}}
    c = controller.GameController(
        a, b, mode="bot_vs_bot", config=cfg, n_games=3, rng=random.Random(1)
    )
    assert c.human_color() is None
    c.start()
    assert c.join(10)
    snap = c.snapshot()
    assert snap.n_games == 3
    assert len(snap.finished_games) == 3
    assert snap.series_result is not None
    assert snap.series_result.score_a + snap.series_result.score_b == 3.0


def test_bot_vs_bot_uses_random_opening():
    c = controller.GameController(
        FirstLegalPlayer("x"),
        FirstLegalPlayer("y"),
        mode="bot_vs_bot",
        config={**CONFIG, "game": {**CONFIG["game"], "max_plies": 6}},
        rng=random.Random(4),
    )
    c.start()
    assert c.join(10)
    game = c.snapshot().finished_games[0]
    assert len(game.opening_moves) == 2


def test_pause_resume_bot_vs_bot():
    c = controller.GameController(
        FirstLegalPlayer("x"),
        FirstLegalPlayer("y"),
        mode="bot_vs_bot",
        config={**CONFIG, "game": {**CONFIG["game"], "max_plies": 40, "random_opening_plies": 0}},
    )
    c.pause()
    c.start()
    time.sleep(0.2)
    assert c.snapshot().paused
    assert c.snapshot().moves == ()
    c.resume()
    assert c.join(10)
    assert c.snapshot().finished_games[0].moves, "sau resume phải đi tiếp tới hết ván"


def test_bot_move_delay_and_fast_stop():
    cfg = {**CONFIG, "ui": {"bot_move_delay_ms": 10_000}}
    c = controller.GameController(
        FirstLegalPlayer("x"), FirstLegalPlayer("y"), mode="bot_vs_bot", config=cfg
    )
    c.start()
    assert wait_until(lambda: len(c.snapshot().moves) >= 3)  # 2 khai cuộc + 1 nước bot
    time.sleep(0.1)
    assert len(c.snapshot().moves) == 3, "đang chờ delay thì chưa đi tiếp"
    t0 = time.monotonic()
    c.stop()
    assert c.join(2), "stop phải cắt ngang thời gian chờ"
    assert time.monotonic() - t0 < 2


def test_changing_bot_move_delay_interrupts_active_wait():
    cfg = {**CONFIG, "ui": {"bot_move_delay_ms": 10_000}}
    c = controller.GameController(
        FirstLegalPlayer("x"),
        FirstLegalPlayer("y"),
        mode="bot_vs_bot",
        config=cfg,
    )
    c.start()
    assert wait_until(lambda: len(c.snapshot().moves) >= 3)
    time.sleep(0.1)
    c.set_bot_move_delay(0)
    assert c.join(3), "setting delay to zero should release an active wait"
    assert c.snapshot().finished


def test_series_snapshot_tracks_seating_and_thinking_side():
    """Best of 3 swaps colours in game 2; the thinking bot is the side to move."""
    seen = []

    class Recorder(FoolsMatePlayer):
        def select_move(self, board):
            snap = holder["controller"].snapshot()
            seen.append((self.bot_id, board.turn, snap.thinking_color, snap.first_is_white))
            return super().select_move(board)

    holder = {}
    a, b = Recorder("A"), Recorder("B")
    cfg = {**CONFIG, "game": {**CONFIG["game"], "random_opening_plies": 0}}
    c = controller.GameController(
        a, b, mode="bot_vs_bot", config=cfg, n_games=3, rng=random.Random(1)
    )
    holder["controller"] = c
    c.start()
    assert c.join(10)
    assert seen
    for bot_id, turn, thinking_color, first_is_white in seen:
        assert thinking_color == turn
        assert first_is_white == ((bot_id == "A") == (turn == chess.WHITE))
    second_game = [row for row in seen if row[0] == "A"][2:4]  # A's moves in game 2
    assert all(not first_is_white for *_, first_is_white in second_game)
