"""Player interfaces and the thread-safe human player."""

from __future__ import annotations

from queue import Empty, Queue
from threading import Lock
from typing import Protocol

import chess

HUMAN_ID = "human"
_CANCEL = object()


class MatchAborted(Exception):
    """Raised when a waiting human player's match is cancelled."""


class Player(Protocol):
    """Interface implemented by tournament players."""

    bot_id: str
    display_name: str

    def select_move(self, board: chess.Board) -> chess.Move:
        """Select a legal move for the current board."""
        ...

    def reset(self) -> None:
        """Reset state between matches."""
        ...


class HumanPlayer:
    """A human player whose moves arrive from another thread."""

    bot_id = HUMAN_ID

    def __init__(self, display_name: str = "Human") -> None:
        self.display_name = display_name
        self._moves: Queue[chess.Move | object] = Queue()
        self._state_lock = Lock()
        self._cancelled = False

    def submit_move(self, move: chess.Move) -> None:
        """Submit a move from the interface thread."""
        with self._state_lock:
            self._moves.put(move)

    def select_move(self, board: chess.Board) -> chess.Move:
        """Wait until a submitted move is legal on the given board."""
        while True:
            with self._state_lock:
                if self._cancelled:
                    raise MatchAborted
            move = self._moves.get()
            with self._state_lock:
                if self._cancelled or move is _CANCEL:
                    raise MatchAborted
            if isinstance(move, chess.Move) and move in board.legal_moves:
                return move

    def cancel(self) -> None:
        """Cancel a waiting or next move selection."""
        with self._state_lock:
            self._cancelled = True
            self._moves.put(_CANCEL)

    def reset(self) -> None:
        """Discard queued moves and clear cancellation."""
        with self._state_lock:
            while True:
                try:
                    self._moves.get_nowait()
                except Empty:
                    break
            self._cancelled = False
