"""Đặc tả backend/ai/base_bot.py — documents/CONTEXT.md §4.1."""

import chess
import pytest

from tests._helpers import require_module

base = require_module("ai.base_bot")


class FirstMoveBot(base.BaseBot):
    bot_id = "first"
    display_name = "First"

    def select_move(self, board):
        self.last_search_info = {"nodes": 1}
        return next(iter(board.legal_moves))


def test_cannot_instantiate_without_select_move():
    class Incomplete(base.BaseBot):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_default_config_and_search_info():
    bot = FirstMoveBot()
    assert bot.config == {}
    assert bot.last_search_info == {}
    assert FirstMoveBot({"k": 1}).config == {"k": 1}


def test_reset_clears_search_info():
    bot = FirstMoveBot()
    bot.select_move(chess.Board())
    assert bot.last_search_info == {"nodes": 1}
    bot.reset()
    assert bot.last_search_info == {}


def test_bot_unavailable_error():
    err = base.BotUnavailableError("thiếu trọng số")
    assert isinstance(err, Exception)
    assert "thiếu trọng số" in str(err)


def test_display_name_can_come_from_the_config():
    assert FirstMoveBot({"display_name": "  Dragon  "}).display_name == "Dragon"
    assert FirstMoveBot({"display_name": ""}).display_name == "First"
    assert FirstMoveBot().display_name == "First"
