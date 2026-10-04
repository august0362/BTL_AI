"""Public interface required of an owner-provided deep RL policy."""

from __future__ import annotations

from typing import Protocol

import chess


class Policy(Protocol):
    """Select a legal move for the side to move."""

    def select_move(self, board: chess.Board) -> chess.Move: ...
