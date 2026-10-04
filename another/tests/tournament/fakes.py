"""Người chơi giả và tiện ích cho test tournament (không phụ thuộc bot thật)."""

import itertools

import chess


class ScriptedPlayer:
    """Đi lần lượt các nước UCI cho trước. Ghi lại số lần reset/select_move."""

    def __init__(self, ucis, bot_id="scripted", display_name="Scripted"):
        self.bot_id = bot_id
        self.display_name = display_name
        self._ucis = list(ucis)
        self._i = 0
        self.reset_calls = 0
        self.select_calls = 0
        self.last_search_info = {}

    def reset(self):
        self.reset_calls += 1
        self._i = 0

    def select_move(self, board):
        self.select_calls += 1
        move = chess.Move.from_uci(self._ucis[self._i])
        self._i += 1
        self.last_search_info = {"depth": self._i}
        return move


class FirstLegalPlayer:
    """Luôn đi nước hợp lệ có UCI nhỏ nhất (tất định)."""

    def __init__(self, bot_id="first", display_name="First"):
        self.bot_id = bot_id
        self.display_name = display_name
        self.last_search_info = {}
        self.select_calls = 0

    def reset(self):
        self.last_search_info = {}

    def select_move(self, board):
        self.select_calls += 1
        self.last_search_info = {"nodes": board.legal_moves.count()}
        return min(board.legal_moves, key=lambda m: m.uci())


class FoolsMatePlayer:
    """Cầm trắng thì tự sát (f3, g4); cầm đen thì chiếu hết (e5, Qh4#). => Bên đen luôn thắng."""

    WHITE = ["f2f3", "g2g4"]
    BLACK = ["e7e5", "d8h4"]

    def __init__(self, bot_id, display_name=None):
        self.bot_id = bot_id
        self.display_name = display_name or bot_id
        self.last_search_info = {}

    def reset(self):
        pass

    def select_move(self, board):
        script = self.WHITE if board.turn == chess.WHITE else self.BLACK
        return chess.Move.from_uci(script[board.fullmove_number - 1])


class CrashingPlayer:
    def __init__(self, bot_id="crash"):
        self.bot_id = bot_id
        self.display_name = "Crash"

    def reset(self):
        pass

    def select_move(self, board):
        raise RuntimeError("boom")


class IllegalPlayer:
    def __init__(self, bot_id="illegal"):
        self.bot_id = bot_id
        self.display_name = "Illegal"

    def reset(self):
        pass

    def select_move(self, board):
        return chess.Move.from_uci("a1a8")


def fake_clock(step=0.5):
    """Đồng hồ giả: mỗi lần gọi tăng `step` giây => mỗi nước nghĩ đúng `step` giây."""
    counter = itertools.count()
    return lambda: next(counter) * step
